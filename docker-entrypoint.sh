#!/bin/sh
set -eu

# Compose передаёт сюда либо api, либо bot; рабочий код приложения не меняется.
case "${1:-api}" in
  api)
    alembic upgrade head
    exec uvicorn api.main:app --host 0.0.0.0 --port "${SITE_PORT:-8000}"
    ;;
  bot)
    exec python -m bot.main
    ;;
  *)
    echo "Неизвестный сервис: $1. Используйте api или bot." >&2
    exit 64
    ;;
esac
