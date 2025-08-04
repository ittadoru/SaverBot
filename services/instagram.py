from .base import BaseDownloader
import yt_dlp
import os
import uuid
from config import DOWNLOAD_DIR
from utils import logger as log


class InstagramDownloader(BaseDownloader):
    async def download(self, url: str, message=None) -> str:
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        log.log_download_start(url)  # Логируем начало загрузки

        from utils import yt_dlp_logger as yt
        from config import ADMIN_ERROR

        ydl_opts = {
            'format': 'mp4',
            'outtmpl': filename,
            'merge_output_format': 'mp4',
            'quiet': False,
            'logger': yt.YTDlpLoggerAdapter(),
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
            'http_chunk_size': 1024 * 1024,
            'nocheckcertificate': True,
            'tls_verify': False,
        }

        import asyncio
        import time

        loop = asyncio.get_running_loop()

        def run_download_with_retries():
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return  # Загрузка прошла успешно
                except yt_dlp.utils.DownloadError as e:
                    log.log_download_error(f"❌ Ошибка yt-dlp (попытка {attempt}/{max_attempts}): {e}")
                except Exception as e:
                    log.log_download_error(f"❌ Непредвиденная ошибка (попытка {attempt}/{max_attempts}): {e}")

                if attempt < max_attempts:
                    time.sleep(5)  # Ждем перед повторной попыткой
                else:
                    raise Exception("🚫 Все попытки загрузки не удались")

        try:
            # Запускаем синхронную загрузку в пуле потоков, чтобы не блокировать event loop
            await loop.run_in_executor(None, run_download_with_retries)
        except Exception as e:
            import traceback

            error_text = f"Ошибка: {e}"
            full_trace = traceback.format_exc()
            log.log_error(error_text)
            log.log_error(full_trace)

            # Отправляем администратору сообщение с ошибкой, если есть доступ к message
            if message is not None:
                try:
                    await message.bot.send_message(
                        ADMIN_ERROR,
                        f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                        parse_mode="HTML"
                    )
                except Exception as send_err:
                    log.log_error(f"Не удалось отправить ошибку админу: {send_err}")
            raise Exception("🚫 Все попытки загрузки не удались")

        log.log_download_complete(filename)  # Логируем успешное завершение
        return filename
