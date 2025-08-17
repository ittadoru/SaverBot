"""Учёт скачиваний по платформам (YouTube / TikTok / Instagram) в PostgreSQL."""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, PrimaryKeyConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base


class PlatformDownload(Base):
    __tablename__ = "platform_downloads"
    user_id = Column(Integer, nullable=False)
    platform = Column(String(32), nullable=False)
    count = Column(Integer, nullable=False, default=0)
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "platform", name="pk_platform_downloads"),
    )


async def increment_platform_download(session: AsyncSession, user_id: int, platform: str) -> None:
    row = await session.get(PlatformDownload, {"user_id": user_id, "platform": platform})
    if row:
        row.count += 1
    else:
        row = PlatformDownload(user_id=user_id, platform=platform, count=1)
        session.add(row)
    await session.commit()


async def get_platform_counts(session: AsyncSession, user_id: int) -> dict[str, int]:
    query = select(PlatformDownload).where(PlatformDownload.user_id == user_id)
    res = await session.execute(query)
    result: dict[str, int] = {}
    for row in res.scalars().all():
        result[row.platform] = row.count
    return result
