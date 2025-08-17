"""Модель промокода и операции: создание, активация, подсчёт и удаление (одного/всех)."""

from sqlalchemy import Column, Integer, String, delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base


class Promocode(Base):
    """Модель промокода."""
    __tablename__ = 'promocodes'
    code = Column(String, primary_key=True)
    duration_days = Column(Integer, nullable=False)
    uses_left = Column(Integer, nullable=False, server_default='1')


async def add_promocode(
    session: AsyncSession, code: str, duration_days: int, uses_left: int = 1
) -> Promocode:
    """
    Создаёт новый промокод с указанным количеством использований.
    """
    promocode = Promocode(
        code=code.upper(),
        duration_days=duration_days,
        uses_left=uses_left
    )
    session.add(promocode)
    await session.commit()
    return promocode


async def activate_promocode(
    session: AsyncSession, user_id: int, code: str
) -> int | None:
    """
    Активирует промокод для пользователя.
    Уменьшает количество использований и удаляет, если они закончились.
    Возвращает длительность подписки в днях или None, если код недействителен.
    """
    # Локальный импорт для избежания циклических зависимостей
    from db.subscribers import add_subscriber_with_duration

    promocode = await session.get(Promocode, code.upper())
    if not promocode or promocode.uses_left <= 0:
        return None

    duration = promocode.duration_days
    await add_subscriber_with_duration(session, user_id, duration)

    promocode.uses_left -= 1
    if promocode.uses_left == 0:
        await session.delete(promocode)

    await session.commit()
    return duration


async def get_promocode(session: AsyncSession, code: str) -> Promocode | None:
    """Возвращает объект Promocode или None."""
    return await session.get(Promocode, code.upper())


async def get_all_promocodes(session: AsyncSession) -> list[Promocode]:
    """Возвращает список всех доступных промокодов."""
    result = await session.execute(select(Promocode).order_by(Promocode.code))
    return list(result.scalars().all())


async def get_active_promocodes_count(session: AsyncSession) -> int:
    """Возвращает количество активных промокодов."""
    query = select(func.count(Promocode.code))
    return await session.scalar(query)


async def remove_promocode(session: AsyncSession, code: str) -> bool:
    """
    Удаляет один промокод по его коду.
    Возвращает True, если удаление прошло успешно, иначе False.
    """
    promocode = await session.get(Promocode, code.upper())
    if promocode:
        await session.delete(promocode)
        await session.commit()
        return True
    return False


async def remove_all_promocodes(session: AsyncSession) -> None:
    """Удаляет все существующие промокоды из базы данных."""
    await session.execute(delete(Promocode))
    await session.commit()
