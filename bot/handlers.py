"""Хендлеры админки: только администраторы, всё остальное игнорируем."""
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, select

from bot.keyboards import (
    group_actions_kb,
    group_form_kb,
    group_levels_kb,
    group_names_kb,
    groups_kb,
    weekdays_kb,
)
from config import settings
from db import Session
from models import Group

router = Router()
router.message.filter(F.from_user.id.in_(settings.admin_ids))
router.callback_query.filter(F.from_user.id.in_(settings.admin_ids))


class GroupForm(StatesGroup):
    menu = State()
    name = State()
    day_of_week = State()
    starts_at = State()
    duration_min = State()
    price = State()
    level = State()
    topic = State()
    description = State()


FIELD_LABELS = {
    "name": "название группы",
    "level": "уровень группы",
    "day_of_week": "день недели",
    "starts_at": "время начала",
    "duration_min": "длительность",
    "price": "цена",
    "topic": "тема встречи",
    "description": "описание встречи",
}


def group_card_text(data: dict) -> str:
    starts_at = data.get("starts_at")
    duration_min = data.get("duration_min")
    price = data.get("price")
    title = "Редактирование группы" if data.get("group_id") else "Новая группа"
    return (
        f"{title}\n\n"
        f"Возраст группы: {data.get('name') or '—'}\n"
        f"Уровень группы: {data.get('level') or '—'}\n"
        f"День недели: {data.get('day_of_week') or '—'}\n"
        f"Время начала: {f'{starts_at:%H:%M}' if starts_at else '—'}\n"
        f"Длительность: {f'{duration_min} мин' if duration_min is not None else '—'}\n"
        f"Цена: {f'{price} ₽' if price is not None else '—'}\n"
        f"Тема встречи: {data.get('topic') or '—'}\n"
        f"Описание встречи: {data.get('description') or '—'}"
    )


async def update_group_card(m: Message, state: FSMContext, delete_input: bool = False):
    data = await state.get_data()
    try:
        await m.bot.edit_message_text(
            chat_id=m.chat.id,
            message_id=data["card_message_id"],
            text=group_card_text(data),
            reply_markup=group_form_kb(),
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise
    prompt_message_id = data.get("prompt_message_id")
    if prompt_message_id is not None:
        await m.bot.delete_message(chat_id=m.chat.id, message_id=prompt_message_id)
    if delete_input:
        await m.bot.delete_message(chat_id=m.chat.id, message_id=m.message_id)
    await state.update_data(prompt_message_id=None)
    await state.set_state(GroupForm.menu)


@router.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer("Админка клуба «Нева-Темза». Управление группами: /groups")


@router.message(Command("groups"))
async def cmd_groups(m: Message):
    async with Session() as s:
        groups = list((await s.execute(select(Group))).scalars().all())
    await m.answer("📚 Группы клуба", reply_markup=groups_kb(groups))


# --- Добавление группы через редактируемую карточку ---

@router.callback_query(F.data == "group:add")
async def group_add(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    card = await cb.message.answer(group_card_text({}), reply_markup=group_form_kb())
    await state.update_data(card_message_id=card.message_id)
    await state.set_state(GroupForm.menu)
    await cb.answer()


@router.callback_query(F.data.startswith("group_form:edit:"))
async def group_edit_field(cb: CallbackQuery, state: FSMContext):
    if "card_message_id" not in await state.get_data():
        await cb.answer("Карточка уже закрыта. Нажмите «Добавить группу» ещё раз.", show_alert=True)
        return

    field = cb.data.removeprefix("group_form:edit:")
    if field == "name":
        form_state, text, keyboard = GroupForm.name, "Название группы:", group_names_kb()
    elif field == "level":
        form_state, text, keyboard = GroupForm.level, "Уровень группы:", group_levels_kb()
    elif field == "day_of_week":
        form_state, text, keyboard = GroupForm.day_of_week, "День недели:", weekdays_kb()
    elif field == "starts_at":
        form_state, text, keyboard = GroupForm.starts_at, "Время начала (ЧЧ:ММ):", None
    elif field == "duration_min":
        form_state, text, keyboard = GroupForm.duration_min, "Длительность в минутах:", None
    elif field == "price":
        form_state, text, keyboard = GroupForm.price, "Цена в рублях:", None
    elif field == "topic":
        form_state, text, keyboard = GroupForm.topic, "Тема встречи:", None
    elif field == "description":
        form_state, text, keyboard = GroupForm.description, "Описание встречи:", None
    else:
        await cb.answer("Неизвестный параметр")
        return

    await state.set_state(form_state)
    prompt = await cb.message.answer(text, reply_markup=keyboard)
    await state.update_data(prompt_message_id=prompt.message_id)
    await cb.answer()


@router.callback_query(GroupForm.name, F.data.startswith("group_form:name:"))
async def group_name(cb: CallbackQuery, state: FSMContext):
    await state.update_data(name=cb.data.removeprefix("group_form:name:"))
    await update_group_card(cb.message, state)
    await cb.answer()


@router.callback_query(GroupForm.day_of_week, F.data.startswith("group_form:day:"))
async def group_day(cb: CallbackQuery, state: FSMContext):
    await state.update_data(day_of_week=cb.data.removeprefix("group_form:day:"))
    await update_group_card(cb.message, state)
    await cb.answer()


@router.message(GroupForm.starts_at)
async def group_time(m: Message, state: FSMContext):
    from datetime import time as dtime
    try:
        hh, mm = map(int, m.text.strip().split(":"))
        t = dtime(hh, mm)
    except ValueError:
        await m.answer("Нужен формат ЧЧ:ММ, например 19:00. Попробуй ещё раз:")
        return
    await state.update_data(starts_at=t)
    await update_group_card(m, state, delete_input=True)


@router.message(GroupForm.duration_min)
async def group_duration(m: Message, state: FSMContext):
    if not m.text.strip().isdigit():
        await m.answer("Число, например 45:")
        return
    await state.update_data(duration_min=int(m.text))
    await update_group_card(m, state, delete_input=True)


@router.message(GroupForm.price)
async def group_price(m: Message, state: FSMContext):
    if not m.text.strip().isdigit():
        await m.answer("Число, например 450:")
        return
    await state.update_data(price=int(m.text))
    await update_group_card(m, state, delete_input=True)


@router.callback_query(GroupForm.level, F.data.startswith("group_form:level:"))
async def group_level(cb: CallbackQuery, state: FSMContext):
    await state.update_data(level=cb.data.removeprefix("group_form:level:"))
    await update_group_card(cb.message, state)
    await cb.answer()


@router.message(GroupForm.topic)
async def group_topic(m: Message, state: FSMContext):
    await state.update_data(topic=m.text.strip())
    await update_group_card(m, state, delete_input=True)


@router.message(GroupForm.description)
async def group_description(m: Message, state: FSMContext):
    await state.update_data(description=m.text.strip())
    await update_group_card(m, state, delete_input=True)


@router.callback_query(F.data == "group_form:save")
async def group_save(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "card_message_id" not in data:
        await cb.answer("Карточка уже закрыта", show_alert=True)
        return

    missing = [label for field, label in FIELD_LABELS.items() if data.get(field) in (None, "")]
    if missing:
        await cb.answer(f"Заполните: {', '.join(missing)}", show_alert=True)
        return

    values = {field: data[field] for field in FIELD_LABELS}
    group_id = data.get("group_id")
    async with Session.begin() as s:
        if group_id is None:
            s.add(Group(**values))
        else:
            group = await s.get(Group, group_id)
            if group is None:
                await cb.answer("Группа не найдена", show_alert=True)
                return
            for field, value in values.items():
                setattr(group, field, value)

    await state.clear()
    async with Session() as s:
        groups = list((await s.execute(select(Group))).scalars().all())
    await cb.message.edit_text("📚 Группы клуба", reply_markup=groups_kb(groups))
    await cb.answer("Группа обновлена ✅" if group_id else "Группа добавлена ✅")


@router.callback_query(F.data == "group_form:back")
async def group_back(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    async with Session() as s:
        groups = list((await s.execute(select(Group))).scalars().all())
    await cb.message.edit_text("📚 Группы клуба", reply_markup=groups_kb(groups))
    await cb.answer()


# --- Просмотр / редактирование / удаление ---

@router.callback_query(F.data == "group:list")
async def group_list(cb: CallbackQuery):
    await cmd_groups(cb.message)


@router.callback_query(F.data.startswith("group:edit:"))
async def group_edit(cb: CallbackQuery, state: FSMContext):
    group_id = int(cb.data.split(":")[2])
    async with Session() as s:
        group = await s.get(Group, group_id)
    if group is None:
        await cb.answer("Группа не найдена", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        group_id=group.id,
        card_message_id=cb.message.message_id,
        **{field: getattr(group, field) for field in FIELD_LABELS},
    )
    await state.set_state(GroupForm.menu)
    await cb.message.edit_text(group_card_text(await state.get_data()), reply_markup=group_form_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("group:del:"))
async def group_delete(cb: CallbackQuery):
    group_id = int(cb.data.split(":")[2])
    async with Session.begin() as s:
        await s.execute(delete(Group).where(Group.id == group_id))
    async with Session() as s:
        groups = list((await s.execute(select(Group))).scalars().all())
    await cb.message.edit_text("📚 Группы клуба", reply_markup=groups_kb(groups))
    await cb.answer("Группа удалена 🗑")


@router.callback_query(F.data.startswith("group:"))
async def group_view(cb: CallbackQuery):
    group_id = int(cb.data.split(":")[1])
    async with Session() as s:
        g = await s.get(Group, group_id)
    if g is None:
        await cb.answer("Группа не найдена")
        return
    await cb.message.answer(
        f"{g.name} · {g.day_of_week} {g.starts_at:%H:%M} · {g.duration_min} мин\n"
        f"Уровень: {g.level}\nЦена: {g.price} ₽\n"
        f"Тема: {g.topic}\nОписание: {g.description}",
        reply_markup=group_actions_kb(g.id),
    )
