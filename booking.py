from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from db import Session
from models import Booking, BookingStatus, Group


async def list_groups() -> list[Group]:
    async with Session() as s:
        return list((await s.execute(select(Group))).scalars().all())


async def create_booking(group_id: int, name: str, phone: str) -> Booking | None:
    """Атомарная запись: не даёт превысить capacity при конкурентных запросах.

    Берём блокировку строки группы (FOR UPDATE), считаем подтверждённые
    записи и вставляем, только если есть место. Возвращает None, если мест нет.
    """
    async with Session.begin() as s:
        group = await s.execute(
            select(Group).where(Group.id == group_id).with_for_update()
        )
        group = group.scalar_one_or_none()
        if group is None:
            return None
        count = await s.execute(
            select(func.count(Booking.id)).where(
                Booking.group_id == group_id, Booking.status != BookingStatus.CANCELLED
            )
        )
        if count.scalar_one() >= group.capacity:
            return None
        booking = Booking(group_id=group_id, name=name, phone=phone)
        s.add(booking)
        await s.flush()
        return booking


async def cancel_booking(booking_id: int) -> bool:
    async with Session.begin() as s:
        res = await s.execute(
            update(Booking)
            .where(Booking.id == booking_id)
            .values(status=BookingStatus.CANCELLED)
        )
        return res.rowcount > 0
