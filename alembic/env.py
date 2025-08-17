"""Alembic настройки миграций: offline/online режим с конвертацией async URL в sync."""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Добавляем корень проекта в PYTHONPATH для импорта моделей
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.base import Base, DATABASE_URL  # noqa: E402  (после добавления пути)
import db  # noqa: F401,E402  (импорт моделей чтобы Alembic «видел» их)

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Запуск миграций в offline-режиме.

    Формирует SQL без подключения к БД (используется URL из ini)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций с подключением к БД.

    Преобразует async URL (asyncpg) в sync (psycopg2) чтобы Alembic мог работать."""
    sync_url = DATABASE_URL.replace("asyncpg", "psycopg2")
    connectable = create_engine(sync_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():  # pragma: no cover - средовой вызов
    run_migrations_offline()
else:  # pragma: no cover
    run_migrations_online()
