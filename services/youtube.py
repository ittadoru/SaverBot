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

        # info = await self.get_video_info(url)
        # logger.info(info)

        # return None
        
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
        """
        Скачивает лучший аудиопоток (m4a/mp4) через pytubefix, без конвертации в mp3.
        Возвращает путь к скачанному m4a-файлу.
        """
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.m4a")
        logger.info("⏬ [AUDIO] start url=%s user_id=%s", url, user_id)
        loop = asyncio.get_running_loop()
        def run_download():
            yt = YouTube(url)
            # Выбираем лучший аудиопоток в mp4/m4a
            stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
            if not stream:
                raise Exception("No audio/mp4 stream found")
            stream.download(output_path=DOWNLOAD_DIR, filename=os.path.basename(filename))
        try:
            await loop.run_in_executor(None, run_download)
        except Exception as e:
            import traceback
            err = str(e)
            logger.error("audio failed err=%s", err)
            logger.error(traceback.format_exc())
            if message:
                await message.bot.send_message(
                    PRIMARY_ADMIN_ID,
                    f"❗️Ошибка аудио:\n<pre>{err}</pre>",
                    parse_mode="HTML",
                )
            raise

        logger.info("✅ [AUDIO] done file=%s", filename)
        return filename
    
    async def get_video_info(self, url: str) -> dict:
        """
        Получить всю информацию о ролике: название, форматы, размеры, наличие аудио/видео, и т.д.
        Возвращает dict с ключами: title, streams (list), length, author, etc.
        """
        loop = asyncio.get_running_loop()
        def fetch():
            yt = YouTube(url)
            info = {
                'title': yt.title,
                'author': yt.author,
                'length': yt.length,
                'views': yt.views,
                'description': yt.description,
                'streams': []
            }
            for s in yt.streams:
                info['streams'].append({
                    'itag': s.itag,
                    'type': s.type,
                    'res': s.resolution,
                    'mime_type': s.mime_type,
                    'progressive': s.is_progressive,
                    'abr': getattr(s, 'abr', None),
                    'filesize': s.filesize,
                    'video_codec': getattr(s, 'video_codec', None),
                    'audio_codec': getattr(s, 'audio_codec', None),
                    'url': s.url
                })
            return info
        return await loop.run_in_executor(None, fetch)
