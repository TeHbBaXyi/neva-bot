from aiogram import Bot

from config import settings
from models import Booking

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.BOT_TOKEN)
    return _bot


async def notify_new_booking(booking: Booking, group_name: str) -> None:
    """Шлёт преподавателю уведомление о новой записи."""
    bot = get_bot()
    text = (
        "🎟 Новая запись!\n"
        f"Группа: {group_name}\n"
        f"Имя: {booking.name}\n"
        f"Телефон: {booking.phone}"
    )
    for admin_id in settings.admin_ids:
        await bot.send_message(admin_id, text)
