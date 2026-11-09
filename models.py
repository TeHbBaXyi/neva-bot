from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))        # Adults / Teens / Kids
    day_of_week: Mapped[str] = mapped_column(String(16))   # воскресенье ...
    starts_at: Mapped[time] = mapped_column(Time)
    duration_min: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)            # рубли
    level: Mapped[str] = mapped_column(String(64))
    topic: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    capacity: Mapped[int] = mapped_column(Integer, default=8)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="group")


class BookingStatus(StrEnum):
    NEW = "new"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(32))
    status: Mapped[BookingStatus] = mapped_column(String(16), default=BookingStatus.NEW)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    group: Mapped[Group] = relationship(back_populates="bookings")
