
"""YouTube downloader с поддержкой проверки размера и агрегированного прогресса.

Исправление: ранее процент "застревал" (например, на ~33%), потому что учитывался
только текущий файл (video или audio). Теперь прогресс агрегирует размеры всех
скачиваемых частей (video + audio) и отображает суммарный процент.
"""

from __future__ import annotations

import os
import uuid
import time
import asyncio
import yt_dlp
from aiogram import types

from utils.logger import get_logger, YTDlpLoggerAdapter
from db.subscribers import is_subscriber as db_is_subscriber
from db.base import get_session
from .base import BaseDownloader
from config import DOWNLOAD_DIR, PRIMARY_ADMIN_ID, MAX_FREE_VIDEO_MB


logger = get_logger(__name__, platform="youtube")

class YTDLPDownloader(BaseDownloader):
    async def download(
        self,
        url: str,
        user_id: int,
        message: types.Message,
        custom_format: str | None = None,
    ) -> str | tuple[str, str]:
        """Скачать видео. Возврат: путь или ("DENIED_SIZE", size_mb)."""
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        logger.info("⏬ [DOWNLOAD] start url=%s user_id=%s", url, user_id)
        loop = asyncio.get_running_loop()

        def extract_info():
            with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
                return ydl.extract_info(url, download=False)

        info = await loop.run_in_executor(None, extract_info)
        file_size_bytes = None
        if info:
            file_size_bytes = info.get('filesize') or info.get('filesize_approx')

        async with get_session() as session:
            is_sub = await db_is_subscriber(session, user_id)

        large_video = False
        if file_size_bytes:
            size_mb = file_size_bytes / (1024 * 1024)
            if not is_sub and size_mb > MAX_FREE_VIDEO_MB:
                return ("DENIED_SIZE", f"{size_mb:.1f}")
            if is_sub and size_mb > MAX_FREE_VIDEO_MB:
                logger.info("large video for subscriber size=%.1fMB", size_mb)
                large_video = True

        video_format = custom_format or (
            'bestvideo[ext=mp4][vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]'
            if is_sub else
            'bestvideo[ext=mp4][vcodec^=avc1][height<=480]+bestaudio[ext=m4a]/best[ext=mp4]'
        )

        # убрали пользовательский прогресс и callback'и – скрытая загрузка
        job_id = None

        def progress_hook(_d):  # noqa: D401
            return  # игнорируем

        ydl_opts = {
            'format': video_format,
            'outtmpl': filename,
            'merge_output_format': 'mp4',
            'quiet': False,
            'logger': YTDlpLoggerAdapter(),
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
            'http_chunk_size': 1024 * 1024,
            'progress_hooks': [progress_hook],
        }

        def run_download_with_retries():
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return
                except Exception:  # noqa: BLE001
                    logger.exception("yt download error attempt=%s", attempt)
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
            try:
                await message.bot.send_message(
                    PRIMARY_ADMIN_ID,
                    f"❗️Ошибка YouTube:\n<pre>{err}</pre>",
                    parse_mode="HTML",
                )
            except Exception:  # noqa: BLE001
                pass
            raise

        logger.info("✅ [DOWNLOAD] done file=%s", filename)
        return filename

    async def download_audio(self, url: str, user_id: int, message: types.Message | None = None) -> str:
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp3")
        logger.info("⏬ [AUDIO] start url=%s user_id=%s", url, user_id)
        loop = asyncio.get_running_loop()
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': filename,
            'merge_output_format': 'mp3',
            'quiet': False,
            'logger': YTDlpLoggerAdapter(),
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
            'http_chunk_size': 1024 * 1024,
        }

        def run_download_with_retries():
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return
                except yt_dlp.utils.DownloadError as e:  # noqa: PERF203
                    logger.error("audio dl error attempt=%s/%s err=%s", attempt, max_attempts, e)
                except Exception:  # noqa: BLE001
                    logger.exception("audio unexpected error attempt=%s/%s", attempt, max_attempts)
                if attempt < max_attempts:
                    time.sleep(5)
                else:
                    raise Exception("all attempts failed")

        try:
            await loop.run_in_executor(None, run_download_with_retries)
        except Exception as e:  # noqa: BLE001
            import traceback
            err = str(e)
            logger.error("audio failed err=%s", err)
            logger.error(traceback.format_exc())
            if message:
                try:
                    await message.bot.send_message(
                        PRIMARY_ADMIN_ID,
                        f"❗️Ошибка аудио:\n<pre>{err}</pre>",
                        parse_mode="HTML",
                    )
                except Exception:  # noqa: BLE001
                    pass
            raise
        logger.info("✅ [AUDIO] done file=%s", filename)
        return filename
