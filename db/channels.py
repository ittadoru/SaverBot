from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    select,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from db.base import Base

CHANNEL_GUARD_FLAG = "channel_guard"


class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True)  # без символа @
    chat_id = Column(Integer, nullable=True)  # можем заполнить позднее
    title = Column(String(255), nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("username", name="uq_channel_username"),
    )

    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, username={self.username}, active={self.active}, required={self.is_required})>"


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    key = Column(String(100), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# -------- CRUD: channels ---------

async def list_channels(session: AsyncSession) -> list[Channel]:
    """Возвращает список всех каналов."""
    result = await session.execute(select(Channel).order_by(Channel.id))
    return list(result.scalars().all())



async def add_channel(session: AsyncSession, username: str) -> Channel:
    """Добавляет новый канал по username (без @)."""
    username = username.lstrip('@').lower().strip()
    channel = Channel(username=username)
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def get_or_create_channel(session: AsyncSession, username: str) -> Channel:
    """Возвращает канал по username или создает новый, если не найден."""
    username = username.lstrip('@').lower().strip()
    result = await session.execute(select(Channel).where(Channel.username == username))
    channel = result.scalars().first()
    if channel:
        return channel
    return await add_channel(session, username)



async def delete_channel(session: AsyncSession, channel_id: int) -> bool:
    """Удаляет канал по id. Возвращает True, если удалено."""
    channel = await session.get(Channel, channel_id)
    if not channel:
        return False
    await session.delete(channel)
    await session.commit()
    return True



async def toggle_channel_required(session: AsyncSession, channel_id: int) -> bool:
    """Инвертирует флаг is_required для канала."""
    channel = await session.get(Channel, channel_id)
    if not channel:
        return False
    channel.is_required = not channel.is_required
    await session.commit()
    return True



async def toggle_channel_active(session: AsyncSession, channel_id: int) -> bool:
    """Инвертирует флаг active для канала."""
    channel = await session.get(Channel, channel_id)
    if not channel:
        return False
    channel.active = not channel.active
    await session.commit()
    return True



async def get_required_active_channels(session: AsyncSession) -> list[Channel]:
    """Возвращает список активных и обязательных каналов."""
    result = await session.execute(
        select(Channel).where(Channel.active.is_(True), Channel.is_required.is_(True))
    )
    return list(result.scalars().all())


# -------- Feature flag ---------

async def is_channel_guard_enabled(session: AsyncSession) -> bool:
    """Проверяет, включён ли глобальный фича-флаг channel_guard."""
    ff = await session.get(FeatureFlag, CHANNEL_GUARD_FLAG)
    return bool(ff and ff.enabled)



async def toggle_channel_guard(session: AsyncSession) -> bool:
    """Инвертирует флаг channel_guard. Возвращает новое значение."""
    ff = await session.get(FeatureFlag, CHANNEL_GUARD_FLAG)
    if not ff:
        ff = FeatureFlag(key=CHANNEL_GUARD_FLAG, enabled=True)
        session.add(ff)
    else:
        ff.enabled = not ff.enabled
    await session.commit()
    return ff.enabled


# -------- Проверка подписки пользователя ---------

@dataclass(slots=True)
class ChannelCheckResult:
    channel: Channel
    is_member: bool



async def check_user_memberships(
    bot,
    user_id: int,
    channels: Sequence[Channel],
) -> list[ChannelCheckResult]:
    """
    Проверяет подписку пользователя на список каналов.
    Возвращает список ChannelCheckResult (channel, is_member).
    """
    results: list[ChannelCheckResult] = []
    for ch in channels:
        ok = False
        try:
            target = ch.chat_id if ch.chat_id else f"@{ch.username}"
            member = await bot.get_chat_member(target, user_id)
            status = getattr(member, 'status', '')
            ok = status in {"member", "administrator", "creator", "restricted"}
        except Exception:  # noqa: BLE001
            ok = False
        results.append(ChannelCheckResult(channel=ch, is_member=ok))
    return results
