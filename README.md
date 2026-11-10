# Нева-Темза: сайт, API и Telegram-бот

Единый репозиторий клуба разговорного английского «Нева-Темза»:

- `site/` — сайт и его изображения;
- `api/` — FastAPI с `GET /api/groups` и `POST /api/booking`;
- `bot/` — Telegram-админка групп с индивидуальной Zoom-ссылкой в режиме polling;
- `booking.py` — атомарная запись с серверным лимитом мест;
- `docker-compose.yml` — профили `local` и `prod`.

Стек: Python 3.12, aiogram 3, FastAPI, SQLAlchemy 2 async, PostgreSQL 17.

## Локальный запуск на Windows

Нужны Docker Desktop, локально установленный PostgreSQL 17, токен от @BotFather и числовой Telegram ID администратора. Контейнер PostgreSQL локально не создаётся: порт 5432 остаётся вашей установленной PostgreSQL 17.

### 1. Создайте базу

Выполните одну команду в PowerShell:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\createdb.exe" -U postgres -h 127.0.0.1 neva_bot
```

Если `createdb` уже добавлен в `PATH`, достаточно `createdb -U postgres neva_bot`. Миграции Alembic автоматически выполняются при запуске API.

### 2. Заполните `.env`

Скопируйте шаблон:

```powershell
copy .env.example .env
```

Откройте `.env` и укажите:

```dotenv
BOT_TOKEN=реальный_токен_от_BotFather
ADMIN_IDS=ваш_числовой_Telegram_ID
DATABASE_URL=postgresql+asyncpg://postgres:пароль_postgres@host.docker.internal:5432/neva_bot
POSTGRES_PASSWORD=

SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=your_address@gmail.com
SMTP_PASSWORD=пароль_приложения_Google
SMTP_FROM=your_address@gmail.com
SMTP_FROM_NAME=Нева—Темза
SMTP_TIMEOUT=15
```

Для Gmail нужен пароль приложения Google, а не обычный пароль от аккаунта: включите двухфакторную аутентификацию и создайте пароль приложения в настройках безопасности. Если SMTP-поля оставить пустыми, запись продолжит работать, но письмо отправляться не будет.

Если в пароле PostgreSQL есть `@`, `:`, `/`, `#` или `?`, его нужно URL-кодировать. Не добавляйте `.env` в Git: файл уже перечислен в `.gitignore`.

### 3. Запустите API и бота

В каталоге репозитория:

```powershell
docker compose --profile local up --build
```

Будут запущены только `api` и `bot`. Проверки:

- Swagger и проверка запуска API: <http://127.0.0.1:8000/docs>;
- Telegram: отправьте боту `/start`, затем `/groups` и создайте группу;
- адрес API сайта находится в `site/config.js` и по умолчанию равен `http://127.0.0.1:8000`.

Остановка: `Ctrl+C`, затем `docker compose --profile local down`. Данные локальной PostgreSQL сохраняются.

Если контейнер не может подключиться к базе, проверьте, что PostgreSQL запущен и принимает подключения Docker Desktop. В `postgresql.conf` должен быть `listen_addresses = '*'`, а в `pg_hba.conf` — разрешение для подсети Docker с методом `scram-sha-256`; после изменения этих файлов перезапустите службу PostgreSQL.

## Дополнительные возможности

У каждой встречи в Telegram-админке есть собственная ссылка Zoom. После записи сайт показывает её участнику вместе с кнопкой копирования, а заявка сохраняет имя, телефон и почту. После миграции существующей базы откройте редактирование уже созданных встреч и укажите их Zoom-ссылки: для старых записей миграция оставляет это поле пустым.

После создания новой записи API отправляет участнику письмо со ссылкой Zoom, датой, временем и ссылкой на управление записью. Повторная отправка той же формы не создаёт новое письмо. Если SMTP не настроен или письмо не отправилось, запись сохраняется, а сайт честно показывает предупреждение и оставляет ссылку на экране. Автоматические напоминания участникам пока не реализованы.

## Деплой на новый VPS одной командой

Нужен новый Ubuntu 24.04 VPS с root-доступом по SSH. Аренда сервера и домена требуется только для публичного запуска; для локальной демонстрации они не нужны.

На своей машине откройте Git Bash или WSL в каталоге репозитория. Локальный `.env` уже должен содержать настоящие `BOT_TOKEN` и `ADMIN_IDS`, после чего выполните:

```bash
./deploy.sh 203.0.113.10
```

Вместо `203.0.113.10` укажите IP вашего VPS. Скрипт:

1. устанавливает Docker, Docker Compose, Nginx и необходимые утилиты;
2. загружает репозиторий в `/opt/neva-bot` без отправки локальной базы и `.git`;
3. создаёт отдельный случайный пароль серверной PostgreSQL;
4. подставляет IP сервера в `site/config.js`;
5. запускает PostgreSQL, API и бота профилем `prod`;
6. настраивает Nginx: сайт на порту 80, `/api/` проксируется в API.

После завершения сайт доступен по `http://IP`, а бот продолжает работать в polling. Повторный `./deploy.sh IP` обновляет код, сохраняет серверный `.env` с паролем БД и Docker-том с данными.

## Домен и HTTPS

1. В DNS-панели регистратора создайте **A-запись** для выбранного домена, например `club.example.com`, с IP вашего VPS. Дождитесь применения DNS.
2. Укажите домен в Nginx:

```bash
ssh root@203.0.113.10 "sed -i 's/server_name _;/server_name club.example.com;/' /etc/nginx/sites-available/neva-bot && nginx -t && systemctl reload nginx"
```

3. Установите Certbot и бесплатный сертификат Let's Encrypt:

```bash
ssh root@203.0.113.10 "apt-get update && apt-get install -y certbot python3-certbot-nginx && certbot --nginx --redirect -d club.example.com"
```

4. Переведите сайт на HTTPS-адрес API того же домена:

```bash
ssh root@203.0.113.10 "sed -i 's#http://203.0.113.10#https://club.example.com#' /opt/neva-bot/site/config.js"
```

Certbot настроит HTTPS и перенаправление с HTTP. Проверить автоматическое продление можно командой `certbot renew --dry-run` на сервере.

## Полезные команды на сервере

```bash
cd /opt/neva-bot
docker compose --profile prod ps
docker compose --profile prod logs -f api
docker compose --profile prod logs -f bot
docker compose --profile prod logs -f db
```

Не удаляйте том `neva_postgres`: в нём хранятся группы и записи. Команда `docker compose --profile prod down` останавливает сервисы, но сама по себе том не удаляет; флаг `-v` использовать нельзя.
