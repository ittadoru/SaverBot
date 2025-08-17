FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc ffmpeg curl postgresql-client && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Отдельный слой для зависимостей (кэшируется пока не меняется requirements.txt)
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Основной код
COPY . .

EXPOSE 8000

# По умолчанию просто запускаем бота (команда может быть переопределена в docker-compose)
CMD ["python", "bot.py"]