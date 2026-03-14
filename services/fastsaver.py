from __future__ import annotations

import os
from typing import Any

import aiofiles
import aiohttp


class FastSaverClient:
    """Client for FastSaverAPI fallback downloads."""

    def __init__(self) -> None:
        self.base_url = (os.getenv("FASTSAVER_BASE_URL") or "https://fastsaverapi.com").strip().rstrip("/")
        self.token = (os.getenv("FASTSAVER_API_TOKEN") or "").strip()
        self.timeout_seconds = int((os.getenv("FASTSAVER_TIMEOUT_SECONDS") or "30").strip())
        self.enabled_for_tiktok = (os.getenv("FASTSAVER_TIKTOK_FALLBACK") or "1").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    async def get_info(self, source_url: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        endpoint = f"{self.base_url}/get-info"
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        params = {"url": source_url, "token": self.token}

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(endpoint, params=params) as response:
                    if response.status != 200:
                        return None
                    payload = await response.json(content_type=None)
        except Exception:
            return None

        if not isinstance(payload, dict) or payload.get("error"):
            return None
        return payload

    @staticmethod
    def pick_download_url(payload: dict[str, Any] | None) -> str | None:
        if not isinstance(payload, dict):
            return None

        for key in ("download_url", "video_url", "url"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value

        media_field = payload.get("medias") or payload.get("media")
        if isinstance(media_field, dict):
            media_field = [media_field]

        if isinstance(media_field, list):
            for item in media_field:
                if not isinstance(item, dict):
                    continue
                for key in ("download_url", "video_url", "url"):
                    value = item.get(key)
                    if isinstance(value, str) and value.startswith(("http://", "https://")):
                        return value
        return None

    async def download_to_file(self, media_url: str, output_path: str) -> bool:
        timeout = aiohttp.ClientTimeout(total=max(self.timeout_seconds, 60))
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }

        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(media_url, allow_redirects=True) as response:
                    if response.status != 200:
                        return False

                    async with aiofiles.open(output_path, "wb") as out:
                        async for chunk in response.content.iter_chunked(1024 * 256):
                            if chunk:
                                await out.write(chunk)
            return True
        except Exception:
            return False
