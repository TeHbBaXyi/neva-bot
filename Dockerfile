FROM python:3.12-slim

# Python сразу пишет логи в stdout и не создаёт лишние .pyc внутри образа.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Зависимости кешируются отдельно от исходников, чтобы сборка была быстрее.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Один образ обслуживает оба процесса; аргумент выбирает API или Telegram-бота.
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
CMD ["api"]
