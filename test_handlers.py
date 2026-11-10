import inspect
import os
import unittest
from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["BOT_TOKEN"] = "123456:TEST"
os.environ["ADMIN_IDS"] = "1"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/test"

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot import handlers
from bot.dates import upcoming_meeting_dates
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
        "meeting_date": upcoming_meeting_dates("Воскресенье", time(20, 0))[0],
        "starts_at": time(20, 0),
        "duration_min": 60,
        "price": 1000,
        "topic": "Free conversation",
        "zoom_url": "https://zoom.us/j/123456789",
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

    async def test_group_bookings_shows_eight_people_in_one_list(self):
        callback = self.callback("group:bookings:5")
        database = self.database_mock()
        database.get.return_value = SimpleNamespace(
            id=5,
            name="Adults",
            day_of_week="Воскресенье",
            meeting_date=date(2026, 11, 8),
            starts_at=time(20, 0),
            capacity=8,
        )
        bookings = [
            SimpleNamespace(
                id=index,
                name=f"Ученик {index}",
                phone=f"+7999000000{index}",
                email=f"student{index}@example.com",
                status="new",
            )
            for index in range(1, 9)
        ]
        database.execute.return_value.scalars.return_value.all.return_value = bookings
        session = self.session_mock(database)

        with patch.object(handlers, "Session", session):
            await handlers.group_bookings(callback)

        callback.message.answer.assert_awaited_once()
        text = callback.message.answer.call_args.args[0]
        self.assertIn("Записано: 8 из 8", text)
        for index in range(1, 9):
            self.assertIn(f"{index}. Ученик {index} — +7999000000{index}", text)
        keyboard = callback.message.answer.call_args.kwargs["reply_markup"]
        self.assertEqual(len(keyboard.inline_keyboard), 1)
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "group:5")

    async def test_zoom_url_rejects_invalid_input(self):
        for value in ("", "zoom.us/j/123", "http://zoom.us/j/123", None, "9" * 2100):
            error = handlers.group_values_error(form_data(zoom_url=value))
            self.assertIsNotNone(error)
        self.assertIsNone(handlers.group_values_error(form_data()))

    async def test_time_rejects_invalid_input(self):
        for value in ("25:00", "19:60", "abc", "", None, "9" * 5000):
            message = SimpleNamespace(text=value, answer=AsyncMock())

            await handlers.group_time(message, self.state)

            message.answer.assert_awaited_once()
        self.assertNotIn("starts_at", await self.state.get_data())

    async def test_numbers_reject_invalid_input(self):
        for value in ("0", "14", "181", "-15", "abc", None, "9" * 5000):
            message = SimpleNamespace(text=value, answer=AsyncMock())
            await handlers.group_duration(message, self.state)
            message.answer.assert_awaited_once()

        for value in ("-1", "100001", "abc", None, "9" * 5000):
            message = SimpleNamespace(text=value, answer=AsyncMock())
            await handlers.group_price(message, self.state)
            message.answer.assert_awaited_once()

        data = await self.state.get_data()
        self.assertNotIn("duration_min", data)
        self.assertNotIn("price", data)

    async def test_text_fields_reject_empty_and_too_long_input(self):
        for handler, max_length in (
            (handlers.group_topic, 255),
            (handlers.group_description, 1000),
        ):
            for value in ("", "   ", "x" * (max_length + 1), None):
                message = SimpleNamespace(text=value, answer=AsyncMock())
                await handler(message, self.state)
                message.answer.assert_awaited_once()

        data = await self.state.get_data()
        self.assertNotIn("topic", data)
        self.assertNotIn("description", data)

    async def test_group_save_rejects_invalid_card_before_database(self):
        callback = self.callback("group_form:save")
        database = self.database_mock()
        session = self.session_mock(database)
        await self.state.update_data(**form_data(duration_min=0))

        with patch.object(handlers, "Session", session):
            await handlers.group_save(callback, self.state)

        database.add.assert_not_called()
        callback.answer.assert_awaited_once_with(
            "Длительность должна быть от 15 до 180 минут",
            show_alert=True,
        )

    def test_upcoming_dates_follow_selected_weekday(self):
        from bot.dates import upcoming_meeting_dates

        dates = upcoming_meeting_dates(
            "Воскресенье",
            time(20, 0),
            now=datetime(2026, 11, 7, 12, 0),
        )

        self.assertEqual(dates, [
            date(2026, 11, 8),
            date(2026, 11, 15),
            date(2026, 11, 22),
            date(2026, 11, 29),
        ])

    def test_upcoming_dates_skip_meeting_that_already_started(self):
        from bot.dates import upcoming_meeting_dates

        dates = upcoming_meeting_dates(
            "Воскресенье",
            time(20, 0),
            now=datetime(2026, 11, 8, 20, 1),
        )

        self.assertEqual(dates[0], date(2026, 11, 15))

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
