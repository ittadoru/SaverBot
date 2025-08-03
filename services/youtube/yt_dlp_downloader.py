from utils import logger as log
from utils import yt_dlp_logger as yt
from utils.redis import is_subscriber
from ..base import BaseDownloader
from config import DOWNLOAD_DIR, ADMIN_ERROR

from aiogram import types
import yt_dlp
import asyncio
import os
import uuid
import time


class YTDLPDownloader(BaseDownloader):
    async def download(self, url: str, user_id: int, message: types.Message, custom_format: str = None) -> str:
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        log.log_download_start(url)

        is_sub = await is_subscriber(user_id)
        if custom_format:
            video_format = custom_format
        else:
            if is_sub:
                video_format = 'bestvideo[ext=mp4][vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]'
            else:
                video_format = 'bestvideo[ext=mp4][vcodec^=avc1][height<=480]+bestaudio[ext=m4a]/best[ext=mp4]'

        ydl_opts = {
            'format': video_format,
            'outtmpl': filename,
            'merge_output_format': 'mp4',
            'quiet': False,
            'logger': yt.YTDlpLoggerAdapter(),
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
            'http_chunk_size': 1024 * 1024,
        }

        loop = asyncio.get_running_loop()
        error_info = {}

        def run_download_with_retries():
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return  # Успешно
                except Exception as e:
                    import traceback
                    error_text = f"Ошибка: {e}"
                    full_trace = traceback.format_exc()
                    log.log_error(error_text)
                    log.log_error(full_trace)
                    
                    error_info['error_text'] = error_text
                    error_info['full_trace'] = full_trace
            
                if attempt < max_attempts:
                    time.sleep(5)  # Подождать перед повтором
                else:
                    raise Exception("🚫 Все попытки загрузки не удались")

        try:
            await loop.run_in_executor(None, run_download_with_retries)
        except Exception as e:
            # Отправить админу подробности ошибки
            import traceback
            error_text = f"Ошибка: {e}"
            full_trace = traceback.format_exc()
            try:
                await message.bot.send_message(
                    ADMIN_ERROR,
                    f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                    parse_mode="HTML"
                )
            except Exception as send_err:
                log.log_error(f"Не удалось отправить ошибку админу: {send_err}")
            raise Exception("🚫 Все попытки загрузки не удались")

        log.log_download_complete(filename)
        return filename

    async def download_audio(self, url: str, user_id: int, message=None) -> str:
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp3")
        log.log_download_start(url)
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': filename,
            'merge_output_format': 'mp3',
            'quiet': False,
            'logger': yt.YTDlpLoggerAdapter(),
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
            'http_chunk_size': 1024 * 1024,
        }
        loop = asyncio.get_running_loop()

        def run_download_with_retries():
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return
                except yt_dlp.utils.DownloadError as e:
                    log.log_download_error(f"❌ У библиотеки ошибка (попытка {attempt}/{max_attempts}): {e}")
                except Exception as e:
                    log.log_download_error(f"❌ Непредвиденная ошибка (попытка {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    time.sleep(5)
                else:
                    raise Exception("🚫 Все попытки загрузки не удались")

        try:
            await loop.run_in_executor(None, run_download_with_retries)
        except Exception as e:
            import traceback
            error_text = f"Ошибка: {e}"
            full_trace = traceback.format_exc()
            log.log_error(error_text)
            log.log_error(full_trace)
            try:
                if message is not None:
                    await message.bot.send_message(
                        ADMIN_ERROR,
                        f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                        parse_mode="HTML"
                    )
            except Exception as send_err:
                log.log_error(f"Не удалось отправить ошибку админу: {send_err}")
            raise Exception("🚫 Все попытки загрузки не удались")

        log.log_download_complete(filename)
        return filename