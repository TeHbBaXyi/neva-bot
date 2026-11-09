"""FastAPI: отдаёт данные групп сайту и принимает записи."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from booking import create_booking, list_groups
from db import init_db
from models import Group
from notify import notify_new_booking


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)


class GroupOut(BaseModel):
    id: int
    name: str
    day_of_week: str
    starts_at: str
    duration_min: int
    price: int
    level: str
    topic: str
    description: str
    booked: int          # сколько занято мест


class BookingIn(BaseModel):
    group_id: int
    name: str
    phone: str


@app.get("/api/groups", response_model=list[GroupOut])
async def api_groups():
    groups = await list_groups()
    return [
        GroupOut(
            id=g.id, name=g.name, day_of_week=g.day_of_week,
            starts_at=g.starts_at.strftime("%H:%M"), duration_min=g.duration_min,
            price=g.price, level=g.level, topic=g.topic, description=g.description,
            booked=len([b for b in g.bookings if b.status != "cancelled"]),
        )
        for g in groups
    ]


@app.post("/api/booking", status_code=201)
async def api_booking(payload: BookingIn):
    booking = await create_booking(payload.group_id, payload.name, payload.phone)
    if booking is None:
        raise HTTPException(status_code=409, detail="Мест нет")
    # TODO: загрузить группу и отправить уведомление преподавателю
    await notify_new_booking(booking, group_name=str(payload.group_id))
    return {"ok": True, "booking_id": booking.id}


if __name__ == "__main__":
    import uvicorn
    from config import settings
    uvicorn.run("api.main:app", host=settings.SITE_HOST, port=settings.SITE_PORT, reload=True)
