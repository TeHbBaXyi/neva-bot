from datetime import date

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from booking import cancel_booking
from config import settings
from db import Session
from models import Booking, BookingStatus, Group
from validation import normalize_phone


router = Router()


def user_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мои записи")],
            [KeyboardButton(text="Найти по номеру Telegram", request_contact=True)],
        ],
        resize_keyboard=True,
    )


def booking_text(booking: Booking) -> str:
    group = booking.group
    return (
        f"{group.name} · {group.meeting_date:%d.%m.%Y} {group.starts_at:%H:%M}\n"
        f"Уровень: {group.level}\n"
        f"Имя: {booking.name}\n"
        f"Телефон: {booking.phone}"
    )


def booking_actions_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отменить запись", callback_data=f"user:cancel:{booking_id}")],
    ])


async def user_bookings(user_id: int) -> list[Booking]:
    async with Session() as session:
        result = await session.execute(
            select(Booking)
            .options(joinedload(Booking.group))
            .join(Booking.group)
            .where(
                Booking.telegram_user_id == user_id,
                Booking.status != BookingStatus.CANCELLED,
                Group.meeting_date >= date.today(),
            )
            .order_by(Group.meeting_date, Group.starts_at)
        )
        return list(result.scalars().all())


def user_bookings_content(bookings: list[Booking]):
    if not bookings:
        return "Активных записей не найдено.", None
    lines = ["Ваши записи:", ""]
    lines.extend(
        f"{index}. {booking.group.name} · "
        f"{booking.group.meeting_date:%d.%m.%Y} {booking.group.starts_at:%H:%M}"
        for index, booking in enumerate(bookings, start=1)
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"Отменить запись №{index}",
            callback_data=f"user:cancel:{booking.id}",
        )]
        for index, booking in enumerate(bookings, start=1)
    ])
    return "\n".join(lines), keyboard


async def show_user_bookings(message: Message, user_id: int, edit: bool = False) -> None:
    bookings = await user_bookings(user_id)
    text, keyboard = user_bookings_content(bookings)
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard or user_menu_kb())


async def owned_booking(booking_id: int, user_id: int) -> Booking | None:
    async with Session() as session:
        return await session.scalar(
            select(Booking)
            .options(joinedload(Booking.group))
            .where(
                Booking.id == booking_id,
                Booking.telegram_user_id == user_id,
                Booking.status != BookingStatus.CANCELLED,
            )
        )


@router.message(CommandStart())
async def user_start(message: Message) -> None:
    token = message.text.partition(" ")[2].strip() if message.text else ""
    if not token:
        text = "Здравствуйте! Здесь можно посмотреть и отменить свои записи."
        if message.from_user.id in settings.admin_ids:
            text += "\nУправление группами: /groups"
        await message.answer(text, reply_markup=user_menu_kb())
        return

    async with Session.begin() as session:
        booking = await session.scalar(
            select(Booking)
            .options(joinedload(Booking.group))
            .where(Booking.manage_token == token)
        )
        if booking is None:
            await message.answer("Ссылка недействительна или запись не найдена.")
            return
        if booking.status == BookingStatus.CANCELLED:
            await message.answer("Эта запись уже отменена.")
            return
        booking.telegram_user_id = message.from_user.id

    await message.answer("Запись привязана к вашему Telegram.", reply_markup=user_menu_kb())
    await message.answer(booking_text(booking), reply_markup=booking_actions_kb(booking.id))


@router.message(Command("my"))
@router.message(F.text == "Мои записи")
async def user_my(message: Message) -> None:
    await show_user_bookings(message, message.from_user.id)


@router.message(F.contact)
async def user_contact(message: Message) -> None:
    if message.contact.user_id != message.from_user.id:
        await message.answer("Отправьте собственный контакт кнопкой ниже.")
        return
    try:
        phone = normalize_phone(message.contact.phone_number)
    except ValueError:
        await message.answer("Не удалось распознать номер телефона.")
        return

    async with Session.begin() as session:
        result = await session.execute(
            select(Booking)
            .options(joinedload(Booking.group))
            .join(Booking.group)
            .where(
                Booking.phone == phone,
                Booking.status != BookingStatus.CANCELLED,
                Group.meeting_date >= date.today(),
            )
        )
        bookings = list(result.scalars().all())
        for booking in bookings:
            booking.telegram_user_id = message.from_user.id

    if not bookings:
        await message.answer(
            "По номеру Telegram активных записей нет. "
            "Если вы указывали другой номер, откройте ссылку из подтверждения записи."
        )
        return
    await show_user_bookings(message, message.from_user.id)


@router.callback_query(F.data == "user:my")
async def user_back(cb: CallbackQuery) -> None:
    await show_user_bookings(cb.message, cb.from_user.id, edit=True)
    await cb.answer()


@router.callback_query(F.data.startswith("user:cancel:"))
async def user_cancel(cb: CallbackQuery) -> None:
    booking_id = int(cb.data.rsplit(":", 1)[1])
    booking = await owned_booking(booking_id, cb.from_user.id)
    if booking is None:
        await cb.answer("Запись недоступна", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, отменить", callback_data=f"user:confirm:{booking.id}")],
        [InlineKeyboardButton(text="Назад", callback_data="user:my")],
    ])
    await cb.message.edit_text(
        f"Отменить эту запись?\n\n{booking_text(booking)}",
        reply_markup=keyboard,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("user:confirm:"))
async def user_confirm_cancel(cb: CallbackQuery) -> None:
    booking_id = int(cb.data.rsplit(":", 1)[1])
    booking = await owned_booking(booking_id, cb.from_user.id)
    if booking is None:
        await cb.answer("Запись недоступна", show_alert=True)
        return
    if not await cancel_booking(booking_id, cb.from_user.id):
        await cb.answer("Запись уже отменена", show_alert=True)
        return

    await cb.message.edit_text(f"Запись отменена.\n\n{booking_text(booking)}")
    for admin_id in settings.admin_ids:
        await cb.bot.send_message(
            admin_id,
            "Запись отменена пользователем\n\n" + booking_text(booking),
        )
    await cb.answer("Запись отменена")
