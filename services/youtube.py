
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
from pytubefix import YouTube
from aiogram import types
import yt_dlp

from utils.logger import get_logger, YTDlpLoggerAdapter
from db.subscribers import is_subscriber as db_is_subscriber
from db.base import get_session
from .base import BaseDownloader
from config import DOWNLOAD_DIR, PRIMARY_ADMIN_ID, MAX_FREE_VIDEO_MB


logger = get_logger(__name__, platform="youtube")

class YTDLPDownloader(BaseDownloader):
    async def download(self, url: str, message, user_id: int | None = None) -> str | tuple[str, str]:
        """
        Скачивание лучшего mp4 (progressive, со звуком) через pytubefix.
        """
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        logger.info("⏬ [DOWNLOAD] start url=%s", url)
        loop = asyncio.get_running_loop()

        yt = YouTube(url)
        # Лог всех доступных потоков
        for stream in yt.streams:
            logger.info(f"id={stream.itag} | type={stream.type} | res={stream.resolution} | ext={stream.mime_type} | progressive={stream.is_progressive} | filesize={stream.filesize}")

        # Лучший mp4 progressive (со звуком)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        if not stream:
            raise Exception("No mp4 progressive stream found")

        filesize_bytes = stream.filesize
        filesize_mb = filesize_bytes / (1024 * 1024) if filesize_bytes else 0
        logger.info(f"[SIZE] video size: {filesize_mb:.2f} MB (bytes={filesize_bytes})")

        is_sub = False
        if user_id is not None and isinstance(user_id, int):
            async with get_session() as session:
                is_sub = await db_is_subscriber(session, user_id)
        logger.info(f"[SUB_CHECK] user_id={user_id} is_sub={is_sub} (expire_at должен быть > now)")
        if not is_sub and filesize_mb > MAX_FREE_VIDEO_MB:
            logger.info(f"DENIED_SIZE: {filesize_mb:.2f} MB > {MAX_FREE_VIDEO_MB} MB (not subscriber)")
            return ("DENIED_SIZE", f"{filesize_mb:.1f}")

        def run_download():
            stream.download(output_path=DOWNLOAD_DIR, filename=os.path.basename(filename))

        try:
            await loop.run_in_executor(None, run_download)
        except Exception as e:
            import traceback
            err = str(e)
            logger.error("download failed err=%s", err)
            logger.error(traceback.format_exc())
            if message:
                try:
                    await message.bot.send_message(
                        PRIMARY_ADMIN_ID,
                        f"❗️Ошибка YouTube:\n<pre>{err}</pre>",
                        parse_mode="HTML",
                    )
                except Exception:
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