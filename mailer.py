import asyncio
import logging
import smtplib
from email.header import Header
from email.message import EmailMessage
from email.utils import formataddr
from enum import StrEnum

from config import settings
from models import Booking, Group

logger = logging.getLogger(__name__)


class ZoomEmailStatus(StrEnum):
    SENT = "sent"
    NOT_CONFIGURED = "not_configured"
    FAILED = "failed"
    NO_ZOOM_URL = "no_zoom_url"
    NOT_SENT = "not_sent"


def _smtp_sender() -> str:
    return settings.SMTP_FROM or settings.SMTP_USERNAME


def _smtp_configured() -> bool:
    return bool(
        settings.SMTP_HOST
        and settings.SMTP_USERNAME
        and settings.SMTP_PASSWORD
        and _smtp_sender()
    )


def _send_message(message: EmailMessage) -> None:
    with smtplib.SMTP_SSL(
        settings.SMTP_HOST,
        settings.SMTP_PORT,
        timeout=settings.SMTP_TIMEOUT,
    ) as smtp:
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


def _build_message(booking: Booking, group: Group, manage_url: str | None) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"Ваша ссылка на Zoom — {group.name}"
    message["From"] = formataddr(
        (str(Header(settings.SMTP_FROM_NAME, "utf-8")), _smtp_sender())
    )
    message["To"] = booking.email

    lines = [
        f"Здравствуйте, {booking.name}!",
        "",
        "Вы записаны на встречу разговорного клуба «Нева—Темза».",
        "",
        f"Группа: {group.name}",
        (
            f"Когда: {group.day_of_week}, "
            f"{group.meeting_date.strftime('%d.%m.%Y')} в "
            f"{group.starts_at.strftime('%H:%M')} (лондонское время)"
        ),
        f"Длительность: {group.duration_min} минут",
        f"Тема: {group.topic}",
        "",
        "Ссылка на Zoom:",
        group.zoom_url,
    ]
    if manage_url:
        lines.extend(["", "Управление записью в Telegram:", manage_url])
    lines.extend(["", "Если планы изменятся, отмените запись заранее через Telegram."])
    message.set_content("\n".join(lines))
    return message


async def send_zoom_link(
    booking: Booking,
    group: Group,
    manage_url: str | None,
) -> ZoomEmailStatus:
    if not _smtp_configured():
        return ZoomEmailStatus.NOT_CONFIGURED

    message = _build_message(booking, group, manage_url)
    try:
        await asyncio.to_thread(_send_message, message)
    except Exception:
        logger.exception(
            "Не удалось отправить Zoom-письмо для booking_id=%s",
            getattr(booking, "id", None),
        )
        return ZoomEmailStatus.FAILED
    return ZoomEmailStatus.SENT
