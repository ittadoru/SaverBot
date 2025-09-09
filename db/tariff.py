from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from db.base import Base


class Tariff(Base):
    """
    Представляет тарифный план подписки.
    id: ID тарифа
    name: название тарифа
    price: цена тарифа
    duration_days: длительность в днях
    """
    __tablename__ = 'tariffs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    star_price = Column(Integer, nullable=False, default=0)
    duration_days = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<Tariff id={self.id} name={self.name} price={self.price} star_price={self.star_price} duration_days={self.duration_days}>"


async def create_tariff(
        session: AsyncSession, name: str, price: int, duration_days: int, star_price: int = 0
    ) -> Tariff:
        """
        Создаёт новый тариф и добавляет его в базу данных.
        """
        new_tariff = Tariff(name=name, price=price, star_price=star_price, duration_days=duration_days)
        session.add(new_tariff)
        try:
            await session.commit()
            await session.refresh(new_tariff)
        except SQLAlchemyError:
            await session.rollback()
            raise
        return new_tariff


async def update_tariff(
    session: AsyncSession,
    tariff_id: int,
    *,
    name: str | None = None,
    price: int | None = None,
    star_price: int | None = None,
    duration_days: int | None = None,
) -> Tariff | None:
    """
    Обновляет указанные поля тарифа. Возвращает обновлённый тариф или None.
    """
    tariff = await session.get(Tariff, tariff_id)
    if not tariff:
        return None
    if name is not None:
        tariff.name = name
    if price is not None:
        tariff.price = price
    if star_price is not None:
        tariff.star_price = star_price
    if duration_days is not None:
        tariff.duration_days = duration_days
    try:
        await session.commit()
        await session.refresh(tariff)
    except SQLAlchemyError:
        await session.rollback()
        raise
    return tariff


async def delete_tariff(session: AsyncSession, tariff_id: int) -> bool:
    """
    Удаляет тариф по его ID.
    """
    tariff = await session.get(Tariff, tariff_id)
    if not tariff:
        return False
    try:
        await session.delete(tariff)
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        return False
    return True


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
