# neva-bot

Бэкенд клуба разговорного английского «Нева-Темза»: Telegram-бот-админка + API записи для сайта.

## Стек
aiogram 3 (бот) · FastAPI (API) · SQLAlchemy 2 async · PostgreSQL

## Запуск локально
1. `copy .env.example .env` → вписать BOT_TOKEN (от @BotFather) и ADMIN_IDS (telegram id администраторов через запятую)
2. Поднять Postgres (Docker): `docker run -d -p 5432:5432 -e POSTGRES_USER=neva -e POSTGRES_PASSWORD=neva -e POSTGRES_DB=neva_bot postgres:16`
3. `pip install -r requirements.txt`
4. Бот: `py -m bot.main` (Windows) / `python -m bot.main`
5. API: `py -m api.main` → сайт смотрит на http://127.0.0.1:8000/api/groups

## Структура
- `bot/` — хендлеры админки (FSM: добавление группы по шагам), клавиатуры
- `api/` — FastAPI: GET /api/groups, POST /api/booking
- `booking.py` — атомарная запись с лимитом мест (SELECT ... FOR UPDATE)
- `notify.py` — уведомления преподавателю
- `models.py`, `db.py`, `config.py` — общие слои

## TODO (следующие фичи)
- [ ] Редактирование группы (сейчас только добавить/удалить/посмотреть)
- [ ] Команда /today — список записанных на сегодня
- [ ] Отмена записи из бота
- [ ] Webhook в проде вместо polling
