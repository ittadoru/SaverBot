FROM python:3.13.5-slim

RUN apt-get update && apt-get install -y redis-server && apt-get clean

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 8000

CMD redis-server --daemonize yes && \
    uvicorn utils.server:app --host 0.0.0.0 --port 8000 & \
    python bot.py
