import asyncio
import os
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from datetime import date, time as dtime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


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

    async def get_me(self):
        return SimpleNamespace(username="neva_test_bot")


async def run_scenario():
    import httpx

    import notify
    from sqlalchemy import text

    from api.main import app
    from bot.user_handlers import user_confirm_cancel, user_start
    from db import Base, Session, engine
    from models import Booking, BookingStatus, Group

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        subprocess.run(["python", "-m", "alembic", "upgrade", "head"], check=True)

        async with Session.begin() as session:
            group = Group(
                name="Adults",
                day_of_week="Воскресенье",
                meeting_date=date.today() + timedelta(days=7),
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

                first_booking_id = None
                first_manage_url = None
                for index in range(8):
                    response = await client.post(
                        "/api/booking",
                        json={
                            "group_id": group_id,
                            "name": "Student",
                            "phone": f"+7999000000{index}",
                        },
                    )
                    assert response.status_code == 201, response.text
                    if index == 0:
                        first_booking_id = response.json()["booking_id"]
                        first_manage_url = response.json()["manage_url"]
                        assert first_manage_url.startswith("https://t.me/neva_test_bot?start=")

                response = await client.post(
                    "/api/booking",
                    json={
                        "group_id": group_id,
                        "name": "  Student  ",
                        "phone": "8 (999) 000-00-00",
                    },
                )
                assert response.status_code == 200, response.text
                assert response.json() == {
                    "ok": True,
                    "booking_id": first_booking_id,
                    "duplicate": True,
                }

                for invalid_payload in (
                    {"group_id": 0, "name": "Student", "phone": "+79990000000"},
                    {"group_id": group_id, "name": "123", "phone": "+79990000000"},
                    {"group_id": group_id, "name": "Student", "phone": "abc"},
                ):
                    response = await client.post("/api/booking", json=invalid_payload)
                    assert response.status_code == 422, response.text

                response = await client.post(
                    "/api/booking",
                    json={
                        "group_id": group_id,
                        "name": "Student",
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

        manage_token = first_manage_url.rsplit("=", 1)[1]
        message = SimpleNamespace(
            text=f"/start {manage_token}",
            from_user=SimpleNamespace(id=777),
            answer=AsyncMock(),
        )
        await user_start(message)
        assert message.answer.await_count == 2

        other_user_callback = SimpleNamespace(
            data=f"user:confirm:{first_booking_id}",
            from_user=SimpleNamespace(id=778),
            message=SimpleNamespace(edit_text=AsyncMock()),
            bot=bot,
            answer=AsyncMock(),
        )
        await user_confirm_cancel(other_user_callback)
        other_user_callback.answer.assert_awaited_once_with(
            "Запись недоступна",
            show_alert=True,
        )

        owner_callback = SimpleNamespace(
            data=f"user:confirm:{first_booking_id}",
            from_user=SimpleNamespace(id=777),
            message=SimpleNamespace(edit_text=AsyncMock()),
            bot=bot,
            answer=AsyncMock(),
        )
        await user_confirm_cancel(owner_callback)
        async with Session() as session:
            cancelled = await session.get(Booking, first_booking_id)
            assert cancelled.status == BookingStatus.CANCELLED
        assert len(bot.messages) == 9
        assert "отменена" in bot.messages[-1][1].lower()
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
