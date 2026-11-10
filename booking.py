from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from db import Session
from models import Booking, BookingStatus, Group


async def list_groups() -> list[Group]:
    async with Session() as s:
        query = (
            select(Group)
            .where(Group.meeting_date >= date.today())
            .options(selectinload(Group.bookings))
            .order_by(Group.meeting_date, Group.starts_at)
        )
        return list((await s.execute(query)).scalars().all())


async def create_booking(
    group_id: int,
    name: str,
    phone: str,
    manage_token: str,
) -> tuple[Booking | None, bool]:
    """Создаёт запись без превышения capacity и дублей одного телефона."""
    async with Session.begin() as s:
        group = await s.execute(
            select(Group).where(Group.id == group_id).with_for_update()
        )
        group = group.scalar_one_or_none()
        if group is None:
            return None, False

        existing = await s.scalar(
            select(Booking).where(
                Booking.group_id == group_id,
                Booking.phone == phone,
                Booking.status != BookingStatus.CANCELLED,
            )
        )
        if existing is not None:
            return existing, False

        count = await s.execute(
            select(func.count(Booking.id)).where(
                Booking.group_id == group_id, Booking.status != BookingStatus.CANCELLED
            )
        )
        if count.scalar_one() >= group.capacity:
            return None, False
        booking = Booking(
            group_id=group_id,
            name=name,
            phone=phone,
            manage_token=manage_token,
        )
        s.add(booking)
        await s.flush()
        return booking, True


async def cancel_booking(booking_id: int, telegram_user_id: int | None = None) -> bool:
    async with Session.begin() as s:
        query = (
            update(Booking)
            .where(Booking.id == booking_id, Booking.status != BookingStatus.CANCELLED)
            .values(status=BookingStatus.CANCELLED)
        )
        if telegram_user_id is not None:
            query = query.where(Booking.telegram_user_id == telegram_user_id)
        res = await s.execute(query)
        return res.rowcount > 0
