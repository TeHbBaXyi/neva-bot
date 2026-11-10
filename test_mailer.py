import os
import unittest
from datetime import date, time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

import mailer
from mailer import ZoomEmailStatus


def smtp_settings(**overrides):
    values = {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": 465,
        "SMTP_USERNAME": "sender@gmail.com",
        "SMTP_PASSWORD": "app-password",
        "SMTP_FROM": "sender@gmail.com",
        "SMTP_FROM_NAME": "Нева—Темза",
        "SMTP_TIMEOUT": 15,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def booking_and_group():
    booking = SimpleNamespace(id=7, name="Анна", email="student@example.com")
    group = SimpleNamespace(
        name="Adults",
        day_of_week="Воскресенье",
        meeting_date=date(2026, 11, 8),
        starts_at=time(20, 0),
        duration_min=60,
        topic="Free conversation",
        zoom_url="https://zoom.us/j/123456789",
    )
    return booking, group


class MailerTest(unittest.IsolatedAsyncioTestCase):
    async def test_zoom_email_is_sent_over_ssl(self):
        booking, group = booking_and_group()
        smtp = MagicMock()
        smtp_factory = MagicMock()
        smtp_factory.return_value.__enter__.return_value = smtp

        with (
            patch.object(mailer, "settings", smtp_settings()),
            patch.object(mailer.smtplib, "SMTP_SSL", smtp_factory),
        ):
            status = await mailer.send_zoom_link(
                booking,
                group,
                "https://t.me/neva_test_bot?start=token",
            )

        self.assertEqual(status, ZoomEmailStatus.SENT)
        smtp_factory.assert_called_once_with("smtp.gmail.com", 465, timeout=15)
        smtp.login.assert_called_once_with("sender@gmail.com", "app-password")
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["To"], "student@example.com")
        self.assertIn("Adults", message["Subject"])
        body = message.get_content()
        self.assertIn(group.zoom_url, body)
        self.assertIn("08.11.2026", body)
        self.assertIn("https://t.me/neva_test_bot?start=token", body)

    async def test_zoom_email_reports_missing_configuration(self):
        booking, group = booking_and_group()
        with (
            patch.object(mailer, "settings", smtp_settings(SMTP_PASSWORD="")),
            patch.object(mailer.smtplib, "SMTP_SSL") as smtp_factory,
        ):
            status = await mailer.send_zoom_link(booking, group, None)

        self.assertEqual(status, ZoomEmailStatus.NOT_CONFIGURED)
        smtp_factory.assert_not_called()

    async def test_zoom_email_reports_smtp_failure(self):
        booking, group = booking_and_group()
        with (
            patch.object(mailer, "settings", smtp_settings()),
            patch.object(mailer.smtplib, "SMTP_SSL", side_effect=OSError("SMTP unavailable")),
            self.assertLogs(mailer.logger, level="ERROR"),
        ):
            status = await mailer.send_zoom_link(booking, group, None)

        self.assertEqual(status, ZoomEmailStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
