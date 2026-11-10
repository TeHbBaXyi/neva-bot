from aiogram import Bot

from config import settings
from models import Booking

_bot: Bot | None = None
_bot_username: str | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.BOT_TOKEN)
    return _bot


async def booking_manage_url(token: str) -> str:
    global _bot_username
    if _bot_username is None:
        me = await get_bot().get_me()
        _bot_username = me.username
    return f"https://t.me/{_bot_username}?start={token}"


async def notify_new_booking(
    booking: Booking,
    group_name: str | None = None,
    day_of_week: str | None = None,
    starts_at: str | None = None,
) -> None:
    """Шлёт преподавателю уведомление о новой записи."""
    bot = get_bot()
    lines = [
        "🎟 Новая запись!",
        f"Имя: {booking.name}",
        f"Телефон: {booking.phone}",
        f"Почта: {booking.email}",
    ]
    if group_name:
        group_info = f"Группа: {group_name}"
        schedule = " ".join(part for part in (day_of_week, starts_at) if part)
        if schedule:
            group_info += f", {schedule}"
        lines.append(group_info)
    for admin_id in settings.admin_ids:
        await bot.send_message(admin_id, "\n".join(lines))
