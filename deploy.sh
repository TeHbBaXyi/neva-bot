#!/usr/bin/env bash
set -euo pipefail

# Единственный аргумент — IP нового Ubuntu VPS.
SERVER_IP="${1:-}"
if [[ -z "$SERVER_IP" ]]; then
  echo "Использование: ./deploy.sh <IP_СЕРВЕРА>" >&2
  exit 64
fi
if [[ ! "$SERVER_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Некорректный IPv4-адрес: $SERVER_IP" >&2
  exit 64
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

for command_name in ssh scp tar; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Не найдена команда: $command_name. Запускайте скрипт в Git Bash или WSL." >&2
    exit 1
  fi
done

if [[ ! -f .env ]]; then
  echo "Сначала создайте .env из .env.example и впишите BOT_TOKEN и ADMIN_IDS." >&2
  exit 1
fi
if ! grep -q '^BOT_TOKEN=.' .env || ! grep -q '^ADMIN_IDS=.' .env; then
  echo "В локальном .env должны быть заполнены BOT_TOKEN и ADMIN_IDS." >&2
  exit 1
fi

SSH_OPTIONS=(-o StrictHostKeyChecking=accept-new)
REMOTE="root@${SERVER_IP}"
REMOTE_DIR="/opt/neva-bot"
UPLOADED_ENV="/tmp/neva-bot.env.upload"

echo "==> Подготавливаю сервер ${SERVER_IP}"
ssh "${SSH_OPTIONS[@]}" "$REMOTE" 'export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get install -y docker.io docker-compose-v2 nginx curl openssl && systemctl enable --now docker nginx'

echo "==> Загружаю код, сайт и изображения"
# .git и локальный .env на сервер не попадают; серверный .env сохраняется между деплоями.
tar -czf - \
  --exclude='./.git' \
  --exclude='./.env' \
  --exclude='./.venv' \
  --exclude='./venv' \
  --exclude='./__pycache__' \
  --exclude='./site/__pycache__' \
  . | ssh "${SSH_OPTIONS[@]}" "$REMOTE" "mkdir -p '$REMOTE_DIR' && tar -xzf - -C '$REMOTE_DIR'"
scp "${SSH_OPTIONS[@]}" .env "$REMOTE:$UPLOADED_ENV"

echo "==> Настраиваю production и запускаю сервисы"
ssh "${SSH_OPTIONS[@]}" "$REMOTE" "bash -s -- '$SERVER_IP'" <<'REMOTE_SCRIPT'
set -euo pipefail

SERVER_IP="$1"
REMOTE_DIR="/opt/neva-bot"
UPLOADED_ENV="/tmp/neva-bot.env.upload"
cd "$REMOTE_DIR"
trap 'rm -f "$UPLOADED_ENV"' EXIT

# Читаем значение без source: содержимое .env не выполняется как shell-код.
read_env_value() {
  local key="$1"
  local file="$2"
  sed -n "s/^${key}=//p" "$file" | tail -n 1
}

BOT_TOKEN="$(read_env_value BOT_TOKEN "$UPLOADED_ENV")"
ADMIN_IDS="$(read_env_value ADMIN_IDS "$UPLOADED_ENV")"
SMTP_HOST="$(read_env_value SMTP_HOST "$UPLOADED_ENV")"
SMTP_PORT="$(read_env_value SMTP_PORT "$UPLOADED_ENV")"
SMTP_USERNAME="$(read_env_value SMTP_USERNAME "$UPLOADED_ENV")"
SMTP_PASSWORD="$(read_env_value SMTP_PASSWORD "$UPLOADED_ENV")"
SMTP_FROM="$(read_env_value SMTP_FROM "$UPLOADED_ENV")"
SMTP_FROM_NAME="$(read_env_value SMTP_FROM_NAME "$UPLOADED_ENV")"
SMTP_TIMEOUT="$(read_env_value SMTP_TIMEOUT "$UPLOADED_ENV")"
DATABASE_URL=""
POSTGRES_PASSWORD=""

# При повторном деплое сохраняем параметры уже работающей серверной базы и SMTP.
if [[ -f .env ]]; then
  DATABASE_URL="$(read_env_value DATABASE_URL .env)"
  POSTGRES_PASSWORD="$(read_env_value POSTGRES_PASSWORD .env)"
  for smtp_key in SMTP_HOST SMTP_PORT SMTP_USERNAME SMTP_PASSWORD SMTP_FROM SMTP_FROM_NAME SMTP_TIMEOUT; do
    if [[ -z "${!smtp_key}" ]]; then
      printf -v "$smtp_key" '%s' "$(read_env_value "$smtp_key" .env)"
    fi
  done
fi

# На первом деплое создаём независимый случайный пароль контейнерной PostgreSQL.
if [[ -z "$DATABASE_URL" || -z "$POSTGRES_PASSWORD" ]]; then
  POSTGRES_PASSWORD="$(openssl rand -hex 24)"
  DATABASE_URL="postgresql+asyncpg://neva:${POSTGRES_PASSWORD}@db:5432/neva_bot"
fi

SMTP_PORT="${SMTP_PORT:-465}"
SMTP_FROM_NAME="${SMTP_FROM_NAME:-Нева—Темза}"
SMTP_TIMEOUT="${SMTP_TIMEOUT:-15}"

umask 077
{
  printf 'BOT_TOKEN=%s\n' "$BOT_TOKEN"
  printf 'ADMIN_IDS=%s\n' "$ADMIN_IDS"
  printf 'DATABASE_URL=%s\n' "$DATABASE_URL"
  printf 'POSTGRES_PASSWORD=%s\n' "$POSTGRES_PASSWORD"
  printf 'SMTP_HOST=%s\n' "$SMTP_HOST"
  printf 'SMTP_PORT=%s\n' "$SMTP_PORT"
  printf 'SMTP_USERNAME=%s\n' "$SMTP_USERNAME"
  printf 'SMTP_PASSWORD=%s\n' "$SMTP_PASSWORD"
  printf 'SMTP_FROM=%s\n' "$SMTP_FROM"
  printf 'SMTP_FROM_NAME=%s\n' "$SMTP_FROM_NAME"
  printf 'SMTP_TIMEOUT=%s\n' "$SMTP_TIMEOUT"
} > .env

# Сайт обращается к API через Nginx на том же IP, без отдельного публичного порта БД.
cat > site/config.js <<CONFIG_EOF
// Адрес публичного API, автоматически установленный deploy.sh.
window.API_BASE_URL = "http://${SERVER_IP}";
CONFIG_EOF

# Единый server block: статика сайта и reverse proxy для API.
cat > /etc/nginx/sites-available/neva-bot <<'NGINX_EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root /opt/neva-bot/site;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location ~ ^/(api/|docs$|openapi\.json$) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX_EOF

ln -sfn /etc/nginx/sites-available/neva-bot /etc/nginx/sites-enabled/neva-bot
rm -f /etc/nginx/sites-enabled/default

# restart: unless-stopped в Compose позволяет API и боту дождаться готовности новой БД.
docker compose --profile prod up -d --build
nginx -t
systemctl reload nginx

# Ждём реальный ответ API, а не просто факт запуска контейнера.
API_READY=0
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/docs >/dev/null 2>&1; then
    API_READY=1
    break
  fi
  sleep 2
done
if [[ "$API_READY" -ne 1 ]]; then
  echo "API не ответил вовремя. Последние логи:" >&2
  docker compose --profile prod logs --tail=50 api db >&2
  exit 1
fi

curl -fsS "http://127.0.0.1/" >/dev/null
docker compose --profile prod ps
REMOTE_SCRIPT

echo "==> Готово: http://${SERVER_IP}/"
echo "Swagger API: http://${SERVER_IP}/docs"
