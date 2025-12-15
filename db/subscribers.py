from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    BigInteger,
    String,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base


class Subscriber(Base):
    """
    Модель подписчика.
    user_id: ID пользователя (BigInteger, внешний ключ на users.id)
    expire_at: Дата окончания подписки (UTC)
    updated_at: Дата последнего обновления (автоматически)
    """
    __tablename__ = 'subscribers'
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True)
    expire_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Subscriber user_id={self.user_id} expire_at={self.expire_at.isoformat() if self.expire_at else None}>"


class ProcessedPayment(Base):
    """
    Сохранённые обработанные платежи (idempotency платежного webhook).
    payment_id: ID платежа (строка, уникальный)
    user_id: ID пользователя
    created_at: Дата создания записи
    """
    __tablename__ = 'processed_payments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(String(100), nullable=False, unique=True)
    user_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint('payment_id', name='uq_processed_payment_payment_id'),
    )

    def __repr__(self) -> str:
        return f"<ProcessedPayment id={self.id} payment_id={self.payment_id} user_id={self.user_id}>"


# --- Управление подписчиками ---

async def get_or_create_subscriber(session: AsyncSession, user_id: int) -> Subscriber:
    """
    Возвращает подписчика или создаёт нового с истёкшей подпиской.
    """
    subscriber = await session.get(Subscriber, user_id)
    if not subscriber:
        subscriber = Subscriber(user_id=user_id, expire_at=datetime.now(timezone.utc))
        session.add(subscriber)
        await session.commit()
    return subscriber

async def add_subscriber_with_duration(session: AsyncSession, user_id: int, days: int) -> Subscriber:
    """
    Добавляет или продлевает подписку пользователя.
    Если подписка активна — продлевает её, иначе создаёт новую.
    """
    now = datetime.now(timezone.utc)
    subscriber = await session.get(Subscriber, user_id)
    base_date = now
    if subscriber and subscriber.expire_at > now:
        base_date = subscriber.expire_at
    new_expire_at = base_date + timedelta(days=days)
    if subscriber:
        subscriber.expire_at = new_expire_at
    else:
        subscriber = Subscriber(user_id=user_id, expire_at=new_expire_at)
        session.add(subscriber)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return subscriber


async def is_subscriber(session: AsyncSession, user_id: int) -> bool:
    """
    Проверяет, есть ли у пользователя активная подписка.
    """
    subscriber = await session.get(Subscriber, user_id)
    return bool(subscriber and subscriber.expire_at > datetime.now(timezone.utc))


async def get_subscriber_expiry(session: AsyncSession, user_id: int) -> datetime | None:
    """
    Возвращает дату окончания подписки пользователя или None.
    """
    subscriber = await session.get(Subscriber, user_id)
    return subscriber.expire_at if subscriber else None


async def get_subscriber(session: AsyncSession, user_id: int) -> Subscriber | None:
    """
    Возвращает объект Subscriber для пользователя или None.
    """
    return await session.get(Subscriber, user_id)


async def get_all_subscribers(session: AsyncSession) -> list[Subscriber]:
    """
    Возвращает список всех подписчиков.
    """
    result = await session.execute(select(Subscriber))
    return list(result.scalars().all())


async def get_total_subscribers(session: AsyncSession) -> int:
    """
    Возвращает общее количество подписчиков.
    """
    return await session.scalar(select(func.count(Subscriber.user_id)))


async def get_subscriptions_count_for_period(session: AsyncSession, days: int) -> int:
    """
    Подсчитывает количество новых/продленных подписок за указанный период (в днях).
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    query = select(func.count(Subscriber.user_id)).where(Subscriber.updated_at >= start_date)
    return await session.scalar(query)


async def delete_subscriber_by_id(session: AsyncSession, user_id: int) -> None:
    """
    Удаляет подписчика по его user_id.
    """
    subscriber = await session.get(Subscriber, user_id)
    if subscriber:
        await session.delete(subscriber)
        try:
            await session.commit()
        except Exception:
            await session.rollback()


 # --- Processed payments (idempotency) ---

async def is_payment_processed(session: AsyncSession, payment_id: str) -> bool:
    """
    Проверяет, записан ли payment_id (уже обработан).
    """
    if not payment_id:
        return False
    result = await session.execute(
        select(ProcessedPayment.id).where(ProcessedPayment.payment_id == payment_id)
    )
    return result.scalar_one_or_none() is not None

async def mark_payment_processed(session: AsyncSession, payment_id: str, user_id: int) -> None:
    """
    Сохраняет payment_id как обработанный (игнорирует дубликат race).
    """
    if not payment_id:
        return
    if await is_payment_processed(session, payment_id):
        return
    session.add(ProcessedPayment(payment_id=payment_id, user_id=user_id))
    try:
        await session.commit()
    except Exception:
        await session.rollback()

async def get_active_subscribers(session: AsyncSession) -> list[Subscriber]:
    """
    Возвращает список подписчиков с активной (не истекшей) подпиской.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Subscriber).where(Subscriber.expire_at > now)
    )
    return list(result.scalars().all())
