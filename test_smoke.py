import asyncio
import os
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from datetime import time as dtime
from unittest.mock import patch


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def postgres_database():
    if database_url := os.environ.get("TEST_DATABASE_URL"):
        yield database_url
        return

    if shutil.which("docker") is None:
        raise RuntimeError(
            "Docker is required to start the test Postgres, "
            "or set TEST_DATABASE_URL to a disposable test database."
        )

    container = f"neva-bot-test-{os.getpid()}"
    port = free_port()
    subprocess.run(
        [
            "docker", "run", "--detach", "--rm", "--name", container,
            "--env", "POSTGRES_USER=neva",
            "--env", "POSTGRES_PASSWORD=neva",
            "--env", "POSTGRES_DB=neva_bot_test",
            "--publish", f"127.0.0.1:{port}:5432",
            "postgres:16",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        deadline = time.monotonic() + 60
        while True:
            ready = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", "neva", "-d", "neva_bot_test"],
                capture_output=True,
                text=True,
            )
            if ready.returncode == 0:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Test Postgres did not become ready within 60 seconds")
            time.sleep(1)
        yield f"postgresql+asyncpg://neva:neva@127.0.0.1:{port}/neva_bot_test"
    finally:
        subprocess.run(
            ["docker", "stop", container],
            check=False,
            capture_output=True,
            text=True,
        )


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, admin_id, text):
        self.messages.append((admin_id, text))


async def run_scenario():
    import httpx

    import notify
    from api.main import app
    from db import Base, Session, engine, init_db
    from models import Group

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await init_db()

        async with Session.begin() as session:
            group = Group(
                name="Adults",
                day_of_week="Воскресенье",
                starts_at=dtime(20, 0),
                duration_min=60,
                price=1000,
                level="Pre-Intermediate / A2",
                topic="Free conversation",
                description="Test group",
                capacity=8,
            )
            session.add(group)
            await session.flush()
            group_id = group.id

        bot = FakeBot()
        transport = httpx.ASGITransport(app=app)
        with patch.object(notify, "get_bot", return_value=bot):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/api/groups")
                assert response.status_code == 200, response.text
                assert response.json()[0]["booked"] == 0

                for index in range(8):
                    response = await client.post(
                        "/api/booking",
                        json={
                            "group_id": group_id,
                            "name": f"Student {index + 1}",
                            "phone": f"+7999000000{index}",
                        },
                    )
                    assert response.status_code == 201, response.text

                response = await client.post(
                    "/api/booking",
                    json={
                        "group_id": group_id,
                        "name": "Student 9",
                        "phone": "+79990000009",
                    },
                )
                assert response.status_code == 409, response.text
                assert response.json()["detail"] == "Мест нет"

                response = await client.get("/api/groups")
                assert response.status_code == 200, response.text
                assert response.json()[0]["booked"] == 8

        assert len(bot.messages) == 8
        admin_id, text = bot.messages[-1]
        assert admin_id == 4242
        assert "Группа: Adults, Воскресенье 20:00" in text
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


def main():
    with postgres_database() as database_url:
        os.environ["DATABASE_URL"] = database_url
        os.environ["BOT_TOKEN"] = "123456:TEST"
        os.environ["ADMIN_IDS"] = "4242"
        asyncio.run(run_scenario())
    print("Smoke test passed")


if __name__ == "__main__":
    main()
