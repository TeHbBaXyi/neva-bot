from datetime import datetime, timedelta


WEEKDAYS = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)


def upcoming_meeting_dates(day_of_week, starts_at=None, now=None):
    now = now or datetime.now()
    days_ahead = (WEEKDAYS.index(day_of_week) - now.weekday()) % 7
    first_date = now.date() + timedelta(days=days_ahead)
    if (
        first_date == now.date()
        and starts_at is not None
        and datetime.combine(first_date, starts_at) <= now
    ):
        first_date += timedelta(days=7)
    return [first_date + timedelta(weeks=index) for index in range(4)]
