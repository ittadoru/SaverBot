"""Модель подписчика и функции продления, проверки статуса и агрегированной статистики."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    delete,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base


class Subscriber(Base):
    __tablename__ = 'subscribers'
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True)
    expire_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProcessedPayment(Base):
    """Сохранённые обработанные платежи (idempotency платежного webhook)."""
    __tablename__ = 'processed_payments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(String(100), nullable=False, unique=True)
    user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint('payment_id', name='uq_processed_payment_payment_id'),
    )


# --- Управление подписчиками ---

async def add_subscriber_with_duration(
    session: AsyncSession, user_id: int, days: int
) -> Subscriber:
    """
    Добавляет или продлевает подписку пользователя.
    Если подписка активна — продлевает её, иначе создаёт новую.
    """
    subscriber = await session.get(Subscriber, user_id)
    now = datetime.now(timezone.utc)

    base_date = now
    if subscriber and subscriber.expire_at > now:
        base_date = subscriber.expire_at

    new_expire_at = base_date + timedelta(days=days)

    if subscriber:
        subscriber.expire_at = new_expire_at
        # Поле updated_at обновится автоматически за счет onupdate=func.now()
    else:
        subscriber = Subscriber(user_id=user_id, expire_at=new_expire_at)
        session.add(subscriber)

    await session.commit()
    return subscriber


async def is_subscriber(session: AsyncSession, user_id: int) -> bool:
    """Проверяет, есть ли у пользователя активная подписка."""
    subscriber = await session.get(Subscriber, user_id)
    return subscriber is not None and subscriber.expire_at > datetime.now(timezone.utc)


async def get_subscriber_expiry(session: AsyncSession, user_id: int) -> datetime | None:
    """Возвращает дату окончания подписки пользователя или None."""
    subscriber = await session.get(Subscriber, user_id)
    return subscriber.expire_at if subscriber else None


async def get_subscriber(session: AsyncSession, user_id: int) -> Subscriber | None:
    """Возвращает объект Subscriber для пользователя или None."""
    return await session.get(Subscriber, user_id)


async def get_all_subscribers(session: AsyncSession) -> list[Subscriber]:
    """Возвращает список всех подписчиков."""
    result = await session.execute(select(Subscriber))
    return list(result.scalars().all())


async def get_total_subscribers(session: AsyncSession) -> int:
    """Возвращает общее количество подписчиков."""
    return await session.scalar(select(func.count(Subscriber.user_id)))


async def get_subscriptions_count_for_period(session: AsyncSession, days: int) -> int:
    """
    Подсчитывает количество новых/продленных подписок за указанный период (в днях).
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    query = select(func.count(Subscriber.user_id)).where(Subscriber.updated_at >= start_date)
    return await session.scalar(query)


async def delete_subscriber_by_id(session: AsyncSession, user_id: int) -> None:
    """Удаляет подписчика по его user_id."""
    subscriber = await session.get(Subscriber, user_id)
    if subscriber:
        await session.delete(subscriber)
        await session.commit()


# --- Processed payments (idempotency) ---

async def is_payment_processed(session: AsyncSession, payment_id: str) -> bool:
    """Проверяет, записан ли payment_id (уже обработан)."""
    if not payment_id:
        return False
    result = await session.execute(
        select(ProcessedPayment.id).where(ProcessedPayment.payment_id == payment_id)
    )
    return result.scalar_one_or_none() is not None


async def mark_payment_processed(session: AsyncSession, payment_id: str, user_id: int) -> None:
    """Сохраняет payment_id как обработанный (игнорирует дубликат race)."""
    if not payment_id:
        return
    exists = await is_payment_processed(session, payment_id)
    if exists:
        return
    session.add(ProcessedPayment(payment_id=payment_id, user_id=user_id))
    try:
        await session.commit()
    except Exception:
        await session.rollback()
