"""Модели пользователя и активности: регистрация/обновление, логирование, выборки и статистика."""

import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from db.base import Base
from db.subscribers import Subscriber


class User(Base):
    """Представляет пользователя бота."""
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=False)
    first_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Флаг «хоть раз платил» и дата первого платежа
    has_paid_ever = Column(Boolean, nullable=False, server_default="false")
    first_paid_at = Column(DateTime(timezone=True), nullable=True)

    activities = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan")


class UserActivity(Base):
    """Фиксирует временные метки активности пользователя."""
    __tablename__ = 'user_activity'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    activity_date = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="activities")


async def add_or_update_user(
    session: AsyncSession, user_id: int, first_name: str | None, username: str | None
) -> User:
    """
    Добавляет нового пользователя или обновляет имя и username существующего.
    Обновляет объект пользователя, чтобы загрузить значения, устанавливаемые сервером.
    """
    user = await session.get(User, user_id)
    if user:
        user.first_name = first_name
        user.username = username
        await session.commit()
        await session.refresh(user)
    else:
        user = User(id=user_id, first_name=first_name, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def log_user_activity(session: AsyncSession, user_id: int) -> None:
    """Логирует активность пользователя."""
    new_activity = UserActivity(user_id=user_id)
    session.add(new_activity)
    await session.commit()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """Получает пользователя по его username."""
    query = select(User).where(User.username == username)
    result = await session.execute(query)
    return result.scalars().first()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Получает пользователя по его ID."""
    return await session.get(User, user_id)


async def get_all_user_ids(
    session: AsyncSession, limit: int | None = None, offset: int | None = None
) -> list[int]:
    """
    Получает список всех user_id из базы данных с возможностью пагинации.
    """
    query = select(User.id).order_by(User.id)
    if limit:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_total_users(session: AsyncSession) -> int:
    """Возвращает общее количество пользователей."""
    return await session.scalar(select(func.count(User.id)))


async def get_active_users_today(session: AsyncSession) -> int:
    """Вычисляет количество уникальных пользователей, активных сегодня."""
    today = datetime.date.today()
    query = select(func.count(func.distinct(UserActivity.user_id))).where(
        func.date(UserActivity.activity_date) == today
    )
    return await session.scalar(query)


async def get_new_users_count_for_period(session: AsyncSession, days: int) -> int:
    """
    Подсчитывает количество новых пользователей за указанный период времени (в днях).
    """
    start_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    query = select(func.count(User.id)).where(User.created_at >= start_date)
    return await session.scalar(query)


async def delete_user_by_id(session: AsyncSession, user_id: int) -> bool:
    """Удаляет пользователя по его ID."""
    user = await session.get(User, user_id)
    if user:
        await session.delete(user)
        await session.commit()
        return True
    return False


async def get_users_by_ids(session: AsyncSession, user_ids: list[int]) -> list[User]:
    """Получает список пользователей по списку их ID."""
    if not user_ids:
        return []
    query = select(User).where(User.id.in_(user_ids))
    result = await session.execute(query)
    return list(result.scalars().all())


async def mark_user_has_paid(session: AsyncSession, user_id: int) -> None:
    """Отмечает пользователя как совершившего хотя бы один платёж (идемпотентно)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    user = await session.get(User, user_id)
    if user:
        if not user.has_paid_ever:
            user.has_paid_ever = True
            if user.first_paid_at is None:
                user.first_paid_at = now
            await session.commit()
    else:  # На случай если где-то не был создан ранее
        user = User(id=user_id, first_name=None, username=None, has_paid_ever=True, first_paid_at=now)
        session.add(user)
        await session.commit()


async def has_user_paid_ever(session: AsyncSession, user_id: int) -> bool:
    """Возвращает True если пользователь когда-либо совершал платеж (флаг установлен)."""
    user = await session.get(User, user_id)
    return bool(user and user.has_paid_ever)


async def get_user_ids_never_paid(session: AsyncSession) -> list[int]:
    """Возвращает список user_id, которые ни разу не оплачивали (has_paid_ever = false)."""
    query = select(User.id).where(User.has_paid_ever.is_(False))  # noqa: E712 SQLAlchemy сравнивает правильно
    result = await session.execute(query)
    return list(result.scalars().all())


async def is_user_exists(session: AsyncSession, user_id: int) -> bool:
    """Проверяет, существует ли пользователь в базе данных."""
    user = await session.get(User, user_id)
    return user is not None


async def get_user_ids_without_subscription(session: AsyncSession) -> list[int]:
    """
    Возвращает список ID пользователей, у которых нет активной подписки.
    Использует LEFT JOIN для эффективного поиска.
    """
    query = (
        select(User.id)
        .outerjoin(Subscriber, User.id == Subscriber.user_id)
        .where(Subscriber.user_id.is_(None))
    )
    result = await session.execute(query)
    return list(result.scalars().all())
