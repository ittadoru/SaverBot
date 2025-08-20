from .base import BaseDownloader
import os
import uuid
import asyncio
import time
import yt_dlp
from aiogram import types
from config import DOWNLOAD_DIR, PRIMARY_ADMIN_ID
from utils.logger import get_logger, YTDlpLoggerAdapter

logger = get_logger(__name__, platform="tiktok")


class TikTokDownloader(BaseDownloader):
    async def download(self, url: str, message: types.Message, user_id: int | None = None) -> str:
        """Скачивание видео с TikTok."""
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
            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return
                except yt_dlp.utils.DownloadError as e:  # noqa: PERF203
                    logger.error("yt-dlp error attempt=%s/%s err=%s", attempt, max_attempts, e)
                except Exception:  # noqa: BLE001
                    logger.exception("unexpected error attempt=%s/%s", attempt, max_attempts)
                if attempt < max_attempts:
                    time.sleep(5)
                else:
                    raise Exception("all attempts failed")

        try:
            await loop.run_in_executor(None, run_download_with_retries)
        except Exception as e:  # noqa: BLE001
            import traceback
            err = str(e)
            logger.error("download failed err=%s", err)
            logger.error(traceback.format_exc())
            if message:
                try:
                    await message.bot.send_message(
                        PRIMARY_ADMIN_ID,
                        f"❗️Ошибка TikTok:\n<pre>{err}</pre>",
                        parse_mode="HTML",
                    )
                except Exception:  # noqa: BLE001
                    pass
            raise

        logger.info("✅ [DOWNLOAD] done file=%s", filename)
        return filename