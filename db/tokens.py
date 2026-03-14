from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, BigInteger, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import DAILY_FREE_TOKENS
from db.base import Base


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


class UserTokenWallet(Base):
    __tablename__ = "user_token_wallets"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    daily_tokens = Column(Integer, nullable=False, default=DAILY_FREE_TOKENS)
    bonus_tokens = Column(Integer, nullable=False, default=0)
    token_x = Column(Integer, nullable=False, default=0)
    daily_refill_date = Column(Date, nullable=False, default=_today_utc)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DailySocialUsage(Base):
    __tablename__ = "daily_social_usage"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, primary_key=True)
    used_count = Column(Integer, nullable=False, default=0)


@dataclass(slots=True)
class TokenSnapshot:
    daily_tokens: int
    bonus_tokens: int
    token_x: int
    daily_refill_date: date

    @property
    def total_tokens(self) -> int:
        return self.daily_tokens + self.bonus_tokens


def _to_snapshot(wallet: UserTokenWallet) -> TokenSnapshot:
    return TokenSnapshot(
        daily_tokens=int(wallet.daily_tokens or 0),
        bonus_tokens=int(wallet.bonus_tokens or 0),
        token_x=int(wallet.token_x or 0),
        daily_refill_date=wallet.daily_refill_date,
    )


async def _get_or_create_wallet(session: AsyncSession, user_id: int) -> UserTokenWallet:
    wallet = await session.get(UserTokenWallet, user_id)
    if wallet:
        return wallet

    wallet = UserTokenWallet(
        user_id=user_id,
        daily_tokens=DAILY_FREE_TOKENS,
        bonus_tokens=0,
        token_x=0,
        daily_refill_date=_today_utc(),
    )
    session.add(wallet)
    await session.flush()
    return wallet


def _apply_daily_refill(wallet: UserTokenWallet) -> bool:
    today = _today_utc()
    if wallet.daily_refill_date == today:
        return False

    wallet.daily_tokens = DAILY_FREE_TOKENS
    wallet.daily_refill_date = today
    return True


async def get_token_snapshot(session: AsyncSession, user_id: int, *, refresh_daily: bool = True) -> TokenSnapshot:
    wallet = await _get_or_create_wallet(session, user_id)
    if refresh_daily and _apply_daily_refill(wallet):
        await session.flush()
    return _to_snapshot(wallet)


async def grant_welcome_token_x(session: AsyncSession, user_id: int, amount: int) -> TokenSnapshot:
    if amount <= 0:
        return await get_token_snapshot(session, user_id)

    wallet = await _get_or_create_wallet(session, user_id)
    _apply_daily_refill(wallet)
    wallet.token_x += int(amount)
    await session.flush()
    return _to_snapshot(wallet)


async def add_bonus_tokens(session: AsyncSession, user_id: int, amount: int) -> TokenSnapshot:
    if amount <= 0:
        return await get_token_snapshot(session, user_id)

    wallet = await _get_or_create_wallet(session, user_id)
    _apply_daily_refill(wallet)
    wallet.bonus_tokens += int(amount)
    await session.flush()
    return _to_snapshot(wallet)


async def add_token_x(session: AsyncSession, user_id: int, amount: int) -> TokenSnapshot:
    if amount <= 0:
        return await get_token_snapshot(session, user_id)

    wallet = await _get_or_create_wallet(session, user_id)
    _apply_daily_refill(wallet)
    wallet.token_x += int(amount)
    await session.flush()
    return _to_snapshot(wallet)


async def spend_tokens(session: AsyncSession, user_id: int, amount: int) -> tuple[bool, TokenSnapshot]:
    if amount <= 0:
        return True, await get_token_snapshot(session, user_id)

    wallet = await _get_or_create_wallet(session, user_id)
    _apply_daily_refill(wallet)

    total = (wallet.daily_tokens or 0) + (wallet.bonus_tokens or 0)
    if total < amount:
        return False, _to_snapshot(wallet)

    spend_from_daily = min(wallet.daily_tokens, amount)
    wallet.daily_tokens -= spend_from_daily
    wallet.bonus_tokens -= amount - spend_from_daily
    await session.flush()
    return True, _to_snapshot(wallet)


async def refund_tokens(session: AsyncSession, user_id: int, amount: int) -> TokenSnapshot:
    if amount <= 0:
        return await get_token_snapshot(session, user_id)
    return await add_bonus_tokens(session, user_id, amount)


async def spend_token_x(session: AsyncSession, user_id: int, amount: int) -> tuple[bool, TokenSnapshot]:
    if amount <= 0:
        return True, await get_token_snapshot(session, user_id)

    wallet = await _get_or_create_wallet(session, user_id)
    _apply_daily_refill(wallet)

    if (wallet.token_x or 0) < amount:
        return False, _to_snapshot(wallet)

    wallet.token_x -= int(amount)
    await session.flush()
    return True, _to_snapshot(wallet)


async def refund_token_x(session: AsyncSession, user_id: int, amount: int) -> TokenSnapshot:
    if amount <= 0:
        return await get_token_snapshot(session, user_id)
    return await add_token_x(session, user_id, amount)


async def exchange_token_x_to_tokens(
    session: AsyncSession,
    user_id: int,
    token_x_amount: int,
    rate: int,
) -> tuple[bool, TokenSnapshot]:
    if token_x_amount <= 0 or rate <= 0:
        return False, await get_token_snapshot(session, user_id)

    ok, snapshot = await spend_token_x(session, user_id, token_x_amount)
    if not ok:
        return False, snapshot

    gained = token_x_amount * rate
    new_snapshot = await add_bonus_tokens(session, user_id, gained)
    return True, new_snapshot


async def _get_or_create_daily_social_usage(
    session: AsyncSession,
    user_id: int,
    usage_date: date,
) -> DailySocialUsage:
    usage = await session.get(DailySocialUsage, {"user_id": user_id, "date": usage_date})
    if usage:
        return usage

    usage = DailySocialUsage(user_id=user_id, date=usage_date, used_count=0)
    session.add(usage)
    await session.flush()
    return usage


async def get_daily_social_usage(session: AsyncSession, user_id: int) -> int:
    row = await _get_or_create_daily_social_usage(session, user_id, _today_utc())
    return int(row.used_count or 0)


async def increment_daily_social_usage(session: AsyncSession, user_id: int, amount: int = 1) -> int:
    if amount <= 0:
        return await get_daily_social_usage(session, user_id)

    row = await _get_or_create_daily_social_usage(session, user_id, _today_utc())
    row.used_count += int(amount)
    await session.flush()
    return int(row.used_count)


async def reset_daily_social_usage(session: AsyncSession, user_id: int) -> int:
    row = await _get_or_create_daily_social_usage(session, user_id, _today_utc())
    row.used_count = 0
    await session.flush()
    return 0


async def get_total_token_x(session: AsyncSession) -> int:
    result = await session.execute(select(func.coalesce(func.sum(UserTokenWallet.token_x), 0)))
    return int(result.scalar_one() or 0)


async def get_total_bonus_tokens(session: AsyncSession) -> int:
    result = await session.execute(select(func.coalesce(func.sum(UserTokenWallet.bonus_tokens), 0)))
    return int(result.scalar_one() or 0)


async def get_wallets_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(UserTokenWallet.user_id)))
    return int(result.scalar_one() or 0)
