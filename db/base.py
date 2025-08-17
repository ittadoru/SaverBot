"""Базовая настройка SQLAlchemy: движок, фабрика асинхронных сессий и декларативная база."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from contextlib import asynccontextmanager

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Управление выводом SQL (по умолчанию выключено, включить можно установив SQL_ECHO=1)
SQL_ECHO = os.getenv("SQL_ECHO", "0").lower() in {"1", "true", "yes", "on"}

engine = create_async_engine(
    DATABASE_URL,
    echo=SQL_ECHO,
    pool_pre_ping=True,  # защищаемся от разорванных соединений
)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

@asynccontextmanager
async def get_session():
    async with async_session() as session:
        yield session