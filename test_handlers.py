import inspect
import os
import unittest
from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["BOT_TOKEN"] = "123456:TEST"
os.environ["ADMIN_IDS"] = "1"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/test"

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot import handlers
from models import Group


def async_context(value):
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=value)
    context.__aexit__ = AsyncMock(return_value=None)
    return context


def form_data(**overrides):
    data = {
        "card_message_id": 10,
        "name": "Adults",
        "level": "Pre-Intermediate / A2",
        "day_of_week": "Воскресенье",
        "starts_at": time(20, 0),
        "duration_min": 60,
        "price": 1000,
        "topic": "Free conversation",
        "description": "Description",
    }
    data.update(overrides)
    return data


class GroupHandlersTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = MemoryStorage()
        self.state = FSMContext(
            self.storage,
            StorageKey(bot_id=1, chat_id=1, user_id=1),
        )

    def callback(self, data):
        return SimpleNamespace(
            data=data,
            message=SimpleNamespace(
                message_id=10,
                answer=AsyncMock(),
                edit_text=AsyncMock(),
            ),
            answer=AsyncMock(),
        )

    def session_mock(self, database):
        session = MagicMock()
        session.begin.return_value = async_context(database)
        session.return_value = async_context(database)
        return session

    def database_mock(self):
        database = MagicMock()
        database.add = MagicMock()
        database.get = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        database.execute = AsyncMock(return_value=result)
        return database

    async def test_group_add_opens_form(self):
        callback = self.callback("group:add")
        callback.message.answer.return_value = SimpleNamespace(message_id=10)

        await handlers.group_add(callback, self.state)

        self.assertEqual(await self.state.get_state(), handlers.GroupForm.menu.state)
        self.assertEqual((await self.state.get_data())["card_message_id"], 10)
        callback.message.answer.assert_awaited_once()
        callback.answer.assert_awaited_once_with()

    async def test_group_save_creates_group(self):
        callback = self.callback("group_form:save")
        database = self.database_mock()
        session = self.session_mock(database)
        await self.state.update_data(**form_data())

        with patch.object(handlers, "Session", session):
            await handlers.group_save(callback, self.state)

        database.add.assert_called_once()
        group = database.add.call_args.args[0]
        self.assertIsInstance(group, Group)
        self.assertEqual(group.name, "Adults")
        self.assertEqual(group.starts_at, time(20, 0))
        self.assertEqual(await self.state.get_data(), {})
        callback.answer.assert_awaited_once_with("Группа добавлена ✅")

    async def test_group_save_updates_existing_group(self):
        callback = self.callback("group_form:save")
        database = self.database_mock()
        database.get.return_value = Group(id=5)
        session = self.session_mock(database)
        await self.state.update_data(**form_data(group_id=5, name="Kids"))

        with patch.object(handlers, "Session", session):
            await handlers.group_save(callback, self.state)

        database.get.assert_awaited_once_with(Group, 5)
        database.add.assert_not_called()
        self.assertEqual(database.get.return_value.name, "Kids")
        callback.answer.assert_awaited_once_with("Группа обновлена ✅")

    async def test_foreign_user_is_rejected_by_router_filter(self):
        callback = SimpleNamespace(from_user=SimpleNamespace(id=999))
        filters = handlers.router.callback_query._handler.filters
        self.assertTrue(filters)

        for access_filter in filters:
            result = access_filter.callback(callback)
            if inspect.isawaitable(result):
                result = await result
            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
