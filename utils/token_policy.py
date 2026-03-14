"""Token economy rules and YouTube pricing helpers."""

from __future__ import annotations

from config import (
    YOUTUBE_DURATION_BUCKETS_SECONDS,
    YOUTUBE_MAX_DURATION_SECONDS,
    YOUTUBE_PRICING,
)


YOUTUBE_QUALITY_ORDER = ("low", "medium", "high")
YOUTUBE_ALLOWED_QUALITIES = set(YOUTUBE_QUALITY_ORDER) | {"audio"}


def get_duration_tier_index(duration_seconds: int) -> int | None:
    """Return tier index by duration or None if duration is out of allowed range."""
    if duration_seconds < 0:
        return None
    if duration_seconds >= YOUTUBE_MAX_DURATION_SECONDS:
        return None

    for idx, bucket in enumerate(YOUTUBE_DURATION_BUCKETS_SECONDS):
        if duration_seconds < bucket:
            return idx
    return None


def get_youtube_price(quality: str, duration_seconds: int) -> tuple[str, int] | None:
    """
    Return tuple (currency, amount) for quality+duration or None if unavailable.
    currency: 'token' or 'token_x'
    """
    quality_key = quality.lower()
    if quality_key not in YOUTUBE_ALLOWED_QUALITIES:
        return None

    tier_index = get_duration_tier_index(duration_seconds)
    if tier_index is None:
        return None

    pricing = YOUTUBE_PRICING.get(quality_key)
    if not pricing:
        return None

    tiers = pricing.get("tiers", ())
    if tier_index >= len(tiers):
        return None

    return pricing["currency"], int(tiers[tier_index])


def format_duration(seconds: int) -> str:
    """Human readable duration format H:MM:SS or M:SS."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
