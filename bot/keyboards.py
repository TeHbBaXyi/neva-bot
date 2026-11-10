from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.dates import WEEKDAYS, upcoming_meeting_dates
from models import Group


def groups_kb(groups: list[Group]) -> InlineKeyboardMarkup:
    """Список групп, отсортированный по дате и времени."""
    days = dict(zip(WEEKDAYS, ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")))
    sorted_groups = sorted(
        groups,
        key=lambda g: (g.meeting_date, g.starts_at, g.name, g.level),
    )
    rows = [
        [InlineKeyboardButton(
            text=(
                f"{g.name} · {g.level.rsplit(' / ', 1)[-1]} · "
                f"{g.meeting_date:%d.%m} · {g.starts_at:%H:%M}"
            ),
            callback_data=f"group:{g.id}",
        )]
        for g in sorted_groups
    ]
    rows.append([InlineKeyboardButton(text="➕ Добавить группу",
                                      callback_data="group:add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def meeting_dates_kb(day_of_week, starts_at=None, now=None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{day_of_week} · {meeting_date:%d.%m.%Y}",
            callback_data=f"group_form:date:{meeting_date.isoformat()}",
        )]
        for meeting_date in upcoming_meeting_dates(day_of_week, starts_at, now)
    ])


def group_actions_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Записавшиеся", callback_data=f"group:bookings:{group_id}")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"group:edit:{group_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"group:del:{group_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="group:list")],
    ])


def group_bookings_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"group:{group_id}")],
    ])


def group_form_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Название", callback_data="group_form:edit:name"),
            InlineKeyboardButton(text="Уровень", callback_data="group_form:edit:level"),
        ],
        [
            InlineKeyboardButton(text="День недели", callback_data="group_form:edit:day_of_week"),
            InlineKeyboardButton(text="Дата", callback_data="group_form:edit:meeting_date"),
        ],
        [InlineKeyboardButton(text="Время", callback_data="group_form:edit:starts_at")],
        [
            InlineKeyboardButton(text="Длительность", callback_data="group_form:edit:duration_min"),
            InlineKeyboardButton(text="Цена", callback_data="group_form:edit:price"),
        ],
        [InlineKeyboardButton(text="Тема встречи", callback_data="group_form:edit:topic")],
        [InlineKeyboardButton(text="Ссылка Zoom", callback_data="group_form:edit:zoom_url")],
        [InlineKeyboardButton(text="Описание встречи", callback_data="group_form:edit:description")],
        [InlineKeyboardButton(text="✅ Сохранить группу", callback_data="group_form:save")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="group_form:back")],
    ])


def group_names_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"group_form:name:{name}")]
        for name in ("Adults", "Teens", "Kids")
    ])


def weekdays_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=day, callback_data=f"group_form:day:{day}")]
        for day in WEEKDAYS
    ])


def group_levels_kb() -> InlineKeyboardMarkup:
    levels = (
        "Elementary / A1",
        "Pre-Intermediate / A2",
        "Pre-Intermediate+ / A2+",
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=level, callback_data=f"group_form:level:{level}")]
        for level in levels
    ])
