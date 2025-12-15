"""Быстрый сценарий инициализации БД БЕЗ Alembic миграций.
Логика:
1. Пытаемся прочитать alembic_version — если таблица есть, считаем что используется Alembic и просто выходим.
2. Если таблицы alembic_version нет – создаём ВСЕ таблицы из Base.metadata (import db).
3. Повторный запуск безопасен (create_all идемпотентно).
"""
from __future__ import annotations

import asyncio
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from db.base import engine, Base
import db  # noqa: F401  # импорт моделей чтобы они попали в metadata


async def ensure_schema() -> None:
    async with engine.begin() as conn:
        has_alembic = True
        try:
            await conn.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
        except SQLAlchemyError:
            has_alembic = False
            await conn.rollback()

        if has_alembic:
            print("[ensure_schema] Alembic detected (alembic_version table exists) — skip create_all().")
            return

        print("[ensure_schema] alembic_version отсутствует — создаём таблицы через Base.metadata.create_all()")
        await conn.run_sync(Base.metadata.create_all)
        print("[ensure_schema] Done.")


def main() -> None:
    asyncio.run(ensure_schema())


if __name__ == "__main__":  # pragma: no cover
    main()
