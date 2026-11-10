from datetime import date, datetime, time
from enum import StrEnum

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))        # Adults / Teens / Kids
    day_of_week: Mapped[str] = mapped_column(String(16))   # воскресенье ...
    meeting_date: Mapped[date] = mapped_column(Date)
    starts_at: Mapped[time] = mapped_column(Time)
    duration_min: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)            # рубли
    level: Mapped[str] = mapped_column(String(64))
    topic: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    zoom_url: Mapped[str] = mapped_column(String(2048))
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
    email: Mapped[str] = mapped_column(String(254))
    status: Mapped[BookingStatus] = mapped_column(String(16), default=BookingStatus.NEW)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    manage_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    group: Mapped[Group] = relationship(back_populates="bookings")
