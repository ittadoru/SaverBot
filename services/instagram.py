from .base import BaseDownloader
import yt_dlp
import os
import uuid
from config import DOWNLOAD_DIR, ADMIN_ERROR
from utils import yt_dlp_logger as yt, logger as log


class InstagramDownloader(BaseDownloader):
    async def download(self, url: str, message) -> str:
        """
        Загрузка видео с Instagram с помощью yt-dlp.
        """
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        log.log_download_start(url)  # Логируем начало загрузки

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
            username = None
            if hasattr(message, 'from_user') and hasattr(message.from_user, 'username'):
                username = message.from_user.username
            elif hasattr(message, 'username'):
                username = message.username
            elif isinstance(message, int):
                username = f'user_id={message}'
            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return  # Загрузка прошла успешно
                except yt_dlp.utils.DownloadError as e:
                    err_str = str(e)
                    # Проверка на age-restricted/18+ видео
                    if any(x in err_str.lower() for x in ["18 years old", "age-restricted", "login required", "restricted video"]):
                        log.log_message(f"[AGE-RESTRICTED] Видео с ограничением: {url} (user: {username})", log_level="warning")
                        # Сообщение пользователю, если возможно
                        if hasattr(message, 'answer'):
                            import asyncio
                            asyncio.run(message.answer("🚫 Это видео недоступно для скачивания, так как имеет возрастные ограничения или требует авторизации в Instagram."))
                        return "AGE_RESTRICTED"
                    log.log_error(f"❌ Ошибка yt-dlp (попытка {attempt}/{max_attempts}): {e}", username)
                except Exception as e:
                    log.log_error(f"❌ Непредвиденная ошибка (попытка {attempt}/{max_attempts}): {e}", username)

                if attempt < max_attempts:
                    time.sleep(5)  # Ждем перед повторной попыткой
                else:
                    raise Exception("🚫 Все попытки загрузки не удались")

        result = await loop.run_in_executor(None, run_download_with_retries)
        if result == "AGE_RESTRICTED":
            return None
        # Ошибки
        log.log_download_complete(filename)  # Логируем успешное завершение
        return filename
