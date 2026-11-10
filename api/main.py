"""FastAPI: отдаёт данные групп сайту и принимает записи."""
import secrets
from datetime import date

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from booking import create_booking, list_groups
from db import Session
from models import Group
from notify import booking_manage_url, notify_new_booking
from validation import normalize_name, normalize_phone


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class GroupOut(BaseModel):
    id: int
    name: str
    day_of_week: str
    meeting_date: date
    starts_at: str
    duration_min: int
    price: int
    level: str
    topic: str
    description: str
    capacity: int
    booked: int          # сколько занято мест


class BookingIn(BaseModel):
    group_id: int = Field(gt=0)
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_name(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


@app.get("/api/groups", response_model=list[GroupOut])
async def api_groups():
    groups = await list_groups()
    return [
        GroupOut(
            id=g.id, name=g.name, day_of_week=g.day_of_week, meeting_date=g.meeting_date,
            starts_at=g.starts_at.strftime("%H:%M"), duration_min=g.duration_min,
            price=g.price, level=g.level, topic=g.topic, description=g.description,
            capacity=g.capacity,
            booked=len([b for b in g.bookings if b.status != "cancelled"]),
        )
        for g in groups
    ]


@app.post("/api/booking", status_code=201)
async def api_booking(payload: BookingIn, response: Response):
    manage_token = secrets.token_urlsafe(32)
    manage_url = await booking_manage_url(manage_token)
    booking, created = await create_booking(
        payload.group_id,
        payload.name,
        payload.phone,
        manage_token,
    )
    if booking is None:
        raise HTTPException(status_code=409, detail="Мест нет")
    if not created:
        response.status_code = 200
        return {"ok": True, "booking_id": booking.id, "duplicate": True}

    async with Session() as s:
        group = await s.scalar(select(Group).where(Group.id == payload.group_id))
    await notify_new_booking(
        booking,
        group_name=group.name if group else None,
        day_of_week=group.day_of_week if group else None,
        starts_at=group.starts_at.strftime("%H:%M") if group else None,
    )
    return {
        "ok": True,
        "booking_id": booking.id,
        "duplicate": False,
        "manage_url": manage_url,
    }


if __name__ == "__main__":
    import uvicorn
    from config import settings
    uvicorn.run("api.main:app", host=settings.SITE_HOST, port=settings.SITE_PORT, reload=True)
