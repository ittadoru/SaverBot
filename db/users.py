import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, BigInteger, String, Boolean, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from sqlalchemy.exc import SQLAlchemyError

from db.base import Base
from db.subscribers import Subscriber


class User(Base):
    """
    Представляет пользователя бота.
    id: ID пользователя
    first_name: имя
    username: username
    created_at: дата регистрации
    has_paid_ever: флаг «хоть раз платил»
    first_paid_at: дата первого платежа
    activities: активности пользователя
    """
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True, autoincrement=False)
    first_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    has_paid_ever = Column(Boolean, nullable=False, server_default="false")
    first_paid_at = Column(DateTime(timezone=True), nullable=True)
    referrer_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    activities = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username} has_paid_ever={self.has_paid_ever}>"


class UserActivity(Base):
    """
    Фиксирует временные метки активности пользователя.
    id: ID активности
    user_id: ID пользователя
    activity_date: дата активности
    user: связь с пользователем
    """
    __tablename__ = 'user_activity'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    activity_date = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="activities")

    def __repr__(self) -> str:
        return f"<UserActivity id={self.id} user_id={self.user_id} activity_date={self.activity_date}>"



async def add_or_update_user(
    session: AsyncSession,
    user_id: int,
    first_name: Optional[str],
    username: Optional[str],
    referrer_id: Optional[int] = None
) -> User:
    """
    Добавляет нового пользователя или обновляет имя и username существующего.
    Если пользователь новый, может установить referrer_id.
    """
    user = await session.get(User, user_id)
    try:
        if user:
            user.first_name = first_name
            user.username = username
            await session.commit()
            await session.refresh(user)
        else:
            user = User(id=user_id, first_name=first_name, username=username, referrer_id=referrer_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)
    except SQLAlchemyError:
        await session.rollback()
        raise
    return user


def get_ref_link(bot_username: str, user_id: int) -> str:
    """
    Генерирует персональную реферальную ссылку для пользователя.
    """
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


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
    """
    Удаляет пользователя по его ID.
    """
    user = await session.get(User, user_id)
    if not user:
        return False
    from sqlalchemy.exc import SQLAlchemyError
    try:
        await session.delete(user)
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        return False
    return True


async def get_users_by_ids(session: AsyncSession, user_ids: list[int]) -> list[User]:
    """Получает список пользователей по списку их ID."""
    if not user_ids:
        return []
    query = select(User).where(User.id.in_(user_ids))
    result = await session.execute(query)
    return list(result.scalars().all())


async def mark_user_has_paid(session: AsyncSession, user_id: int) -> None:
    """
    Отмечает пользователя как совершившего хотя бы один платёж (идемпотентно).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    user = await session.get(User, user_id)
    try:
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
    except SQLAlchemyError:
        await session.rollback()


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
    Возвращает список ID пользователей, у которых нет активной подписки (нет подписки или истекла).
    """
    now = datetime.now(datetime.timezone.utc)
    query = (
        select(User.id)
        .outerjoin(Subscriber, User.id == Subscriber.user_id)
        .where(
            (Subscriber.user_id.is_(None)) |
            (Subscriber.expire_at <= now)
        )
    )
    result = await session.execute(query)
    return list(result.scalars().all())

async def log_user_activity(session: AsyncSession, user_id: int) -> None:
    """
    Логирует активность пользователя (создаёт запись UserActivity).
    """
    activity = UserActivity(user_id=user_id)
    session.add(activity)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise


async def get_top_referrers(session: AsyncSession, limit: int = 10):
    """
    Возвращает топ пользователей по количеству рефералов (id, username, ref_count, уровень).
    """
    # Подсчёт количества рефералов для каждого пользователя
    subq = (
        select(User.referrer_id.label('referrer_id'), func.count(User.id).label('ref_count'))
        .where(User.referrer_id.isnot(None))
        .group_by(User.referrer_id)
        .subquery()
    )
    # Присоединяем к User, чтобы получить username и id
    query = (
        select(
            User.id,
            User.username,
            subq.c.ref_count
        )
        .join(subq, User.id == subq.c.referrer_id)
        .order_by(subq.c.ref_count.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    rows = result.all()
    # Для каждого — вычисляем уровень (по вашей логике)
    top = []
    for row in rows:
        ref_count = row.ref_count or 0
        # Логика уровней (совпадает с get_referral_stats)
        if ref_count >= 30:
            level = 5
        elif ref_count >= 10:
            level = 4
        elif ref_count >= 3:
            level = 3
        elif ref_count >= 1:
            level = 2
        else:
            level = 1
        top.append(type('TopRef', (), {
            'id': row.id,
            'username': row.username,
            'ref_count': ref_count,
            'level': level
        }))
    return top