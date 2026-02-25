from .base import BaseDownloader
import os
import uuid
import asyncio
import time
import yt_dlp
from aiogram import types
from config import DOWNLOAD_DIR
from utils.logger import get_logger, YTDlpLoggerAdapter

logger = get_logger(__name__, platform="tiktok")


class TikTokDownloader(BaseDownloader):
    async def download(
        self,
        url: str,
        message: types.Message | None = None,
        user_id: int | None = None,
    ) -> str | tuple[str, str] | None:
        """Скачивание видео с TikTok."""
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        logger.info("⬇️ [DOWNLOAD] start url=%s", url)
        loop = asyncio.get_running_loop()
        cookies_path = (os.environ.get("TIKTOK_COOKIES_PATH") or os.environ.get("COOKIES_PATH") or "").strip()
        proxy = (os.environ.get("TIKTOK_PROXY") or os.environ.get("YTDLP_PROXY") or "").strip()

        ydl_opts = {
            "format": "mp4",
            "outtmpl": filename,
            "merge_output_format": "mp4",
            "quiet": False,
            "logger": YTDlpLoggerAdapter(),
            "retries": 10,
            "fragment_retries": 10,
            "socket_timeout": 30,
            "http_chunk_size": 1024 * 1024,
            "nocheckcertificate": True,
            "tls_verify": False,
        }
        if proxy:
            ydl_opts["proxy"] = proxy
            logger.info("🌐 [DOWNLOAD] Используется proxy для TikTok")
        if cookies_path:
            if os.path.isfile(cookies_path):
                ydl_opts["cookiefile"] = cookies_path
                logger.info("🍪 [DOWNLOAD] Используется cookiefile для TikTok: %s", cookies_path)
            else:
                logger.warning("⚠️ [DOWNLOAD] TIKTOK_COOKIES_PATH/COOKIES_PATH не найден: %s", cookies_path)

        def classify_download_error(err_str: str) -> str:
            if "your ip address is blocked from accessing this post" in err_str:
                return "IP_BLOCKED"
            if any(
                x in err_str
                for x in (
                    "login required",
                    "private",
                    "requested content is not available",
                    "not available",
                    "cookies",
                )
            ):
                return "LOGIN_REQUIRED"
            return "RETRY"

        def run_download_with_retries():
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return "OK"
                except yt_dlp.utils.DownloadError as e:  # noqa: PERF203
                    err_str = str(e).lower()
                    status = classify_download_error(err_str)
                    if status == "IP_BLOCKED":
                        logger.warning("⚠️ [DOWNLOAD] TikTok блокирует IP сервера: url=%s", url)
                        return status
                    if status == "LOGIN_REQUIRED":
                        logger.warning("⚠️ [DOWNLOAD] TikTok требует логин/cookies: url=%s", url)
                        return status
                    logger.error("yt-dlp error attempt=%s/%s err=%s", attempt, max_attempts, e)
                except Exception:  # noqa: BLE001
                    logger.exception("unexpected error attempt=%s/%s", attempt, max_attempts)
                if attempt < max_attempts:
                    time.sleep(5)
            return "FAILED"

        status = await loop.run_in_executor(None, run_download_with_retries)
        if status == "IP_BLOCKED":
            return ("IP_BLOCKED", "TikTok заблокировал IP адрес сервера")
        if status == "LOGIN_REQUIRED":
            return ("LOGIN_REQUIRED", "TikTok требует cookies/авторизацию")
        if status != "OK":
            logger.error("download failed after retries url=%s", url)
            return None

        logger.info("✅ [DOWNLOAD] done file=%s", filename)
        return filename
