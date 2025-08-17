from .base import BaseDownloader
import os
import uuid
import asyncio
import time
import yt_dlp
from config import DOWNLOAD_DIR
from utils.logger import get_logger, YTDlpLoggerAdapter

logger = get_logger(__name__, platform="instagram")


class InstagramDownloader(BaseDownloader):
    async def download(self, url: str, message, user_id: int | None = None) -> str | None:
        """Загрузка видео с Instagram с помощью yt-dlp. Возвращает путь к файлу или None при AGE_RESTRICTED."""
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        logger.info("⏬ [DOWNLOAD] start url=%s", url)
        loop = asyncio.get_running_loop()

        ydl_opts = {
            'format': 'mp4',
            'outtmpl': filename,
            'merge_output_format': 'mp4',
            'quiet': False,
            'logger': YTDlpLoggerAdapter(),
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
            'http_chunk_size': 1024 * 1024,
            'nocheckcertificate': True,
            'tls_verify': False,
        }

        def run_download_with_retries():
            max_attempts = 3
            username = None
            if hasattr(message, 'from_user') and getattr(message.from_user, 'username', None):
                username = message.from_user.username
            elif hasattr(message, 'username'):
                username = getattr(message, 'username', None)
            elif isinstance(message, int):
                username = f'user_id={message}'
            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return None
                except yt_dlp.utils.DownloadError as e:  # noqa: PERF203
                    err_str = str(e)
                    if any(x in err_str.lower() for x in ("18 years old", "age-restricted", "login required", "restricted video")):
                        logger.warning("AGE_RESTRICTED url=%s user=%s", url, username)
                        return "AGE_RESTRICTED"
                    logger.error("yt-dlp error attempt=%s/%s err=%s", attempt, max_attempts, e)
                except Exception:  # noqa: BLE001
                    logger.exception("unexpected error attempt=%s/%s", attempt, max_attempts)
                if attempt < max_attempts:
                    time.sleep(5)
                else:
                    raise Exception("all attempts failed")

        result = await loop.run_in_executor(None, run_download_with_retries)
        if result == "AGE_RESTRICTED":
            return None
        logger.info("✅ [DOWNLOAD] done file=%s", filename)
        return filename
