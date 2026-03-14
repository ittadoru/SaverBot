from __future__ import annotations

import logging

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint, func, select, delete
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base

logger = logging.getLogger(__name__)
_missing_table_warned = False


class MediaCache(Base):
    __tablename__ = "media_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(1024), nullable=False, index=True)
    media_type = Column(String(16), nullable=False)  # video | audio
    quality = Column(String(32), nullable=False, default="default")
    file_id = Column(String(255), nullable=False)
    created_by_user_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("url", "media_type", "quality", name="uq_media_cache_key"),
    )


def _norm_media_type(media_type: str) -> str:
    value = (media_type or "").strip().lower()
    return value if value in {"video", "audio"} else "video"


def _norm_quality(quality: str | None) -> str:
    value = (quality or "default").strip().lower()
    return value or "default"


def _is_media_cache_missing(exc: ProgrammingError) -> bool:
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    if sqlstate == "42P01":
        return True
    text = str(exc).lower()
    return "undefinedtableerror" in text or 'relation "media_cache" does not exist' in text


def _warn_missing_table_once() -> None:
    global _missing_table_warned
    if not _missing_table_warned:
        logger.warning("media_cache table is missing in current DB. Cache is temporarily disabled.")
        _missing_table_warned = True


async def get_cached_file_id(
    session: AsyncSession,
    *,
    url: str,
    media_type: str,
    quality: str | None,
) -> str | None:
    query = (
        select(MediaCache.file_id)
        .where(
            MediaCache.url == (url or "")[:1024],
            MediaCache.media_type == _norm_media_type(media_type),
            MediaCache.quality == _norm_quality(quality),
        )
        .limit(1)
    )
    try:
        result = await session.execute(query)
        return result.scalar_one_or_none()
    except ProgrammingError as exc:
        if _is_media_cache_missing(exc):
            await session.rollback()
            _warn_missing_table_once()
            return None
        raise


async def upsert_cached_media(
    session: AsyncSession,
    *,
    url: str,
    media_type: str,
    quality: str | None,
    file_id: str,
    created_by_user_id: int | None = None,
) -> MediaCache | None:
    file_id = (file_id or "").strip()
    if not file_id:
        return None

    try:
        normalized_url = (url or "")[:1024]
        normalized_media_type = _norm_media_type(media_type)
        normalized_quality = _norm_quality(quality)

        row = (
            await session.execute(
                select(MediaCache).where(
                    MediaCache.url == normalized_url,
                    MediaCache.media_type == normalized_media_type,
                    MediaCache.quality == normalized_quality,
                )
            )
        ).scalar_one_or_none()

        if row:
            row.file_id = file_id
            if created_by_user_id is not None:
                row.created_by_user_id = created_by_user_id
            await session.flush()
            return row

        row = MediaCache(
            url=normalized_url,
            media_type=normalized_media_type,
            quality=normalized_quality,
            file_id=file_id,
            created_by_user_id=created_by_user_id,
        )
        session.add(row)
        await session.flush()
        return row
    except ProgrammingError as exc:
        if _is_media_cache_missing(exc):
            await session.rollback()
            _warn_missing_table_once()
            return None
        raise


async def delete_cached_media(
    session: AsyncSession,
    *,
    url: str,
    media_type: str,
    quality: str | None,
) -> None:
    try:
        await session.execute(
            delete(MediaCache).where(
                MediaCache.url == (url or "")[:1024],
                MediaCache.media_type == _norm_media_type(media_type),
                MediaCache.quality == _norm_quality(quality),
            )
        )
        await session.flush()
    except ProgrammingError as exc:
        if _is_media_cache_missing(exc):
            await session.rollback()
            _warn_missing_table_once()
            return
        raise
