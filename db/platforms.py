from __future__ import annotations

from sqlalchemy import Column, Integer, BigInteger, String, PrimaryKeyConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.platform_detect import detect_platform

from db.downloads import DownloadLink
from db.base import Base


class PlatformDownload(Base):
    __tablename__ = "platform_downloads"
    user_id = Column(BigInteger, nullable=False)
    platform = Column(String(32), nullable=False)
    count = Column(Integer, nullable=False, default=0)
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "platform", name="pk_platform_downloads"),
    )

    def __repr__(self) -> str:
        return f"<PlatformDownload user_id={self.user_id} platform={self.platform} count={self.count}>"



async def get_or_create_platform_download(session: AsyncSession, user_id: int, platform: str) -> PlatformDownload:
    row = await session.get(PlatformDownload, {"user_id": user_id, "platform": platform})
    if row:
        return row
    row = PlatformDownload(user_id=user_id, platform=platform, count=0)
    session.add(row)
    await session.flush()
    return row

async def increment_platform_download(session: AsyncSession, user_id: int, platform: str) -> None:
    """Увеличивает счётчик скачиваний по платформе для пользователя."""
    row = await get_or_create_platform_download(session, user_id, platform)
    row.count += 1
    await session.commit()



async def get_platform_counts(session: AsyncSession, user_id: int) -> dict[str, int]:
    """Возвращает словарь: {platform: count} для пользователя."""
    query = select(PlatformDownload).where(PlatformDownload.user_id == user_id)
    res = await session.execute(query)
    result: dict[str, int] = {}
    for row in res.scalars().all():
        result[row.platform] = row.count
    return result



PLATFORMS = ["youtube", "tiktok", "instagram"]

async def get_top_platform_downloads(session: AsyncSession) -> dict[str, int]:
    """
    Возвращает количество скачиваний по платформам (по всем пользователям).
    dict: {platform: count}
    """
    result = {p: 0 for p in PLATFORMS}
    q = select(DownloadLink.url)
    rows = (await session.execute(q)).scalars().all()
    for platform in PLATFORMS:
        result[platform] = sum(1 for url in rows if detect_platform(url) == platform)
    return result