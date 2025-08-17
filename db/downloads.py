"""Учёт количества загрузок пользователей (дневной лимит и общий счётчик) в PostgreSQL.

Для упрощения: одна таблица с уникальной строкой per (user_id, date) для дневного счётчика
и отдельное поле total_downloads для общего числа.
"""
from __future__ import annotations

import datetime
from sqlalchemy import Column, Integer, Date, BigInteger, PrimaryKeyConstraint, select, func, String, DateTime
import datetime as dt
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base


class DailyDownload(Base):
    __tablename__ = "daily_downloads"
    user_id = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "date", name="pk_daily_downloads"),
    )


class TotalDownload(Base):
    __tablename__ = "total_downloads"
    user_id = Column(Integer, primary_key=True)
    total = Column(BigInteger, nullable=False, default=0)


class DownloadLink(Base):
    """Хранит последние ссылки пользователя ( максимум N по времени )."""
    __tablename__ = "user_download_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False)
    url = Column(String(1024), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)


async def get_daily_downloads(session: AsyncSession, user_id: int) -> int:
    today = datetime.date.today()
    row = await session.get(DailyDownload, {"user_id": user_id, "date": today})
    return row.count if row else 0


async def increment_daily_download(session: AsyncSession, user_id: int) -> None:
    today = datetime.date.today()
    row = await session.get(DailyDownload, {"user_id": user_id, "date": today})
    if row:
        row.count += 1
    else:
        row = DailyDownload(user_id=user_id, date=today, count=1)
        session.add(row)
    await session.commit()


async def increment_download(session: AsyncSession, user_id: int) -> None:
    row = await session.get(TotalDownload, user_id)
    if row:
        row.total += 1
    else:
        row = TotalDownload(user_id=user_id, total=1)
        session.add(row)
    await session.commit()


async def get_total_downloads(session: AsyncSession, user_id: int) -> int:
    row = await session.get(TotalDownload, user_id)
    return row.total if row else 0


async def get_top_downloaders(session: AsyncSession, limit: int = 10) -> list[tuple[int, int]]:
    query = select(TotalDownload.user_id, TotalDownload.total).order_by(TotalDownload.total.desc()).limit(limit)
    res = await session.execute(query)
    return list(res.all())



MAX_STORED_LINKS = 10
async def add_download_link(session: AsyncSession, user_id: int, url: str) -> None:
    session.add(DownloadLink(user_id=user_id, url=url[:1024]))
    await session.flush()
    # Оставляем только последние MAX_STORED_LINKS
    subq = (
        select(DownloadLink.id)
        .where(DownloadLink.user_id == user_id)
        .order_by(DownloadLink.created_at.desc())
        .offset(MAX_STORED_LINKS)
    )
    to_delete = await session.execute(subq)
    ids = [r[0] for r in to_delete.all()]
    if ids:
        from sqlalchemy import delete
        await session.execute(delete(DownloadLink).where(DownloadLink.id.in_(ids)))
    await session.commit()


async def get_last_links(session: AsyncSession, user_id: int, limit: int = 3) -> list[str]:
    q = (
        select(DownloadLink.url)
        .where(DownloadLink.user_id == user_id)
        .order_by(DownloadLink.created_at.desc())
        .limit(limit)
    )
    rows = await session.execute(q)
    return [r[0] for r in rows.all()]
