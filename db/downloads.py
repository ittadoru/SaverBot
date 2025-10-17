from __future__ import annotations

import datetime
from sqlalchemy import (
    Column, 
    Integer, 
    Date, 
    BigInteger, 
    PrimaryKeyConstraint, 
    select, 
    String, 
    DateTime
)
import datetime as dt
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base


class DailyDownload(Base):
    __tablename__ = "daily_downloads"
    user_id = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "date", name="pk_daily_downloads"),
    )

    def __repr__(self) -> str:
        return f"<DailyDownload user_id={self.user_id} date={self.date} count={self.count}>"


class TotalDownload(Base):
    __tablename__ = "total_downloads"
    user_id = Column(BigInteger, primary_key=True)
    total = Column(BigInteger, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<TotalDownload user_id={self.user_id} total={self.total}>"


class DownloadLink(Base):
    """Хранит последние ссылки пользователя (максимум N по времени)."""
    __tablename__ = "user_download_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    url = Column(String(1024), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<DownloadLink id={self.id} user_id={self.user_id} url={self.url[:20]}...>"



async def get_daily_downloads(session: AsyncSession, user_id: int) -> int:
    """Возвращает количество загрузок пользователя за сегодня."""
    today = datetime.date.today()
    row = await session.get(DailyDownload, {"user_id": user_id, "date": today})
    return row.count if row else 0



async def get_or_create_daily_download(session: AsyncSession, user_id: int, date: datetime.date) -> DailyDownload:
    row = await session.get(DailyDownload, {"user_id": user_id, "date": date})
    if row:
        return row
    row = DailyDownload(user_id=user_id, date=date, count=0)
    session.add(row)
    await session.flush()
    return row

async def increment_daily_download(session: AsyncSession, user_id: int) -> None:
    """Увеличивает дневной счётчик загрузок пользователя."""
    today = datetime.date.today()
    row = await get_or_create_daily_download(session, user_id, today)
    row.count += 1
    await session.commit()



async def get_or_create_total_download(session: AsyncSession, user_id: int) -> TotalDownload:
    row = await session.get(TotalDownload, user_id)
    if row:
        return row
    row = TotalDownload(user_id=user_id, total=0)
    session.add(row)
    await session.flush()
    return row

async def increment_download(session: AsyncSession, user_id: int) -> None:
    """Увеличивает общий счётчик загрузок пользователя."""
    row = await get_or_create_total_download(session, user_id)
    row.total += 1
    await session.commit()



async def get_total_downloads(session: AsyncSession, user_id: int) -> int:
    """Возвращает общее количество загрузок пользователя."""
    row = await session.get(TotalDownload, user_id)
    return row.total if row else 0



async def get_top_downloaders(session: AsyncSession, limit: int = 10) -> list[tuple[int, int]]:
    """Возвращает топ пользователей по количеству загрузок."""
    query = select(TotalDownload.user_id, TotalDownload.total).order_by(TotalDownload.total.desc()).limit(limit)
    res = await session.execute(query)
    return list(res.all())




MAX_STORED_LINKS = 10

async def add_download_link(session: AsyncSession, user_id: int, url: str) -> None:
    """Добавляет ссылку пользователя и хранит только последние MAX_STORED_LINKS."""
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



async def get_last_links(
    session: AsyncSession, user_id: int, limit: int = 3, include_time: bool = False
) -> list[str] | list[tuple[str, datetime.datetime]]:
    """Возвращает последние ссылки пользователя (до `limit` штук).

    Если include_time=False (по умолчанию) возвращает list[str] с URL.
    Если include_time=True возвращает list[tuple[url, created_at]].
    """
    if include_time:
        q = (
            select(DownloadLink.url, DownloadLink.created_at)
            .where(DownloadLink.user_id == user_id)
            .order_by(DownloadLink.created_at.desc())
            .limit(limit)
        )
        rows = await session.execute(q)
        return [(r[0], r[1]) for r in rows.all()]

    q = (
        select(DownloadLink.url)
        .where(DownloadLink.user_id == user_id)
        .order_by(DownloadLink.created_at.desc())
        .limit(limit)
    )
    rows = await session.execute(q)
    return [r[0] for r in rows.all()]
