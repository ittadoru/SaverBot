"""Модель тарифного плана и CRUD-операции для управления тарифами."""

from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base


class Tariff(Base):
    """Представляет тарифный план подписки."""
    __tablename__ = 'tariffs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    duration_days = Column(Integer, nullable=False)


async def create_tariff(
    session: AsyncSession, name: str, price: int, duration_days: int
) -> Tariff:
    """
    Создаёт новый тариф и добавляет его в базу данных.
    """
    new_tariff = Tariff(name=name, price=price, duration_days=duration_days)
    session.add(new_tariff)
    await session.commit()
    await session.refresh(new_tariff)
    return new_tariff


async def update_tariff(
    session: AsyncSession,
    tariff_id: int,
    *,
    name: str | None = None,
    price: int | None = None,
    duration_days: int | None = None,
) -> Tariff | None:
    """Обновляет указанные поля тарифа. Возвращает обновлённый тариф или None."""
    tariff = await session.get(Tariff, tariff_id)
    if not tariff:
        return None
    if name is not None:
        tariff.name = name
    if price is not None:
        tariff.price = price
    if duration_days is not None:
        tariff.duration_days = duration_days
    await session.commit()
    await session.refresh(tariff)
    return tariff


async def delete_tariff(session: AsyncSession, tariff_id: int) -> bool:
    """
    Удаляет тариф по его ID.
    """
    tariff = await session.get(Tariff, tariff_id)
    if tariff:
        await session.delete(tariff)
        await session.commit()
        return True
    return False


async def get_tariff_by_id(session: AsyncSession, tariff_id: int) -> Tariff | None:
    """
    Получает один тариф по его ID.
    """
    return await session.get(Tariff, tariff_id)


async def get_all_tariffs(session: AsyncSession) -> list[Tariff]:
    """
    Получает все тарифы из базы данных, отсортированные по цене по возрастанию.
    """
    query = select(Tariff).order_by(Tariff.price)
    result = await session.execute(query)
    return list(result.scalars().all())
