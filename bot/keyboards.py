from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models import Group


def groups_kb(groups: list[Group]) -> InlineKeyboardMarkup:
    """Список групп, отсортированный по дню недели и времени."""
    days = {
        "Понедельник": "Пн",
        "Вторник": "Вт",
        "Среда": "Ср",
        "Четверг": "Чт",
        "Пятница": "Пт",
        "Суббота": "Сб",
        "Воскресенье": "Вс",
    }
    day_order = {day: index for index, day in enumerate(days)}
    sorted_groups = sorted(
        groups,
        key=lambda g: (day_order.get(g.day_of_week, 7), g.starts_at, g.name, g.level),
    )
    rows = [
        [InlineKeyboardButton(
            text=(
                f"{g.name} · {g.level.rsplit(' / ', 1)[-1]} · "
                f"{days.get(g.day_of_week, g.day_of_week)} · {g.starts_at:%H:%M}"
            ),
            callback_data=f"group:{g.id}",
        )]
        for g in sorted_groups
    ]
    rows.append([InlineKeyboardButton(text="➕ Добавить группу",
                                      callback_data="group:add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def group_actions_kb(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"group:edit:{group_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"group:del:{group_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="group:list")],
    ])


def group_form_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Название", callback_data="group_form:edit:name"),
            InlineKeyboardButton(text="Уровень", callback_data="group_form:edit:level"),
        ],
        [
            InlineKeyboardButton(text="День недели", callback_data="group_form:edit:day_of_week"),
            InlineKeyboardButton(text="Время", callback_data="group_form:edit:starts_at"),
        ],
        [
            InlineKeyboardButton(text="Длительность", callback_data="group_form:edit:duration_min"),
            InlineKeyboardButton(text="Цена", callback_data="group_form:edit:price"),
        ],
        [InlineKeyboardButton(text="Тема встречи", callback_data="group_form:edit:topic")],
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
    days = (
        "Понедельник", "Вторник", "Среда", "Четверг",
        "Пятница", "Суббота", "Воскресенье",
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=day, callback_data=f"group_form:day:{day}")]
        for day in days
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
