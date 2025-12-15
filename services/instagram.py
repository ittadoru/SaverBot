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
        logger.info("⬇️ [DOWNLOAD] Начало скачивания: url=%s", url)
        loop = asyncio.get_running_loop()

        # Поддержка cookies / логина через переменные окружения
        cookies_path = os.environ.get('COOKIES_PATH')
        insta_username = os.environ.get('INSTAGRAM_USERNAME')
        insta_password = os.environ.get('INSTAGRAM_PASSWORD')

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

        # Если задан файл cookies — передаём в yt-dlp
        if cookies_path:
            ydl_opts['cookiefile'] = cookies_path
        # Если заданы учётные данные — передаём их
        if insta_username and insta_password:
            ydl_opts['username'] = insta_username
            ydl_opts['password'] = insta_password

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
                    err_str = str(e).lower()
                    if any(x in err_str for x in ("18 years old", "age-restricted", "restricted video")):
                        logger.warning("⚠️ [DOWNLOAD] Ограничение по возрасту (AGE_RESTRICTED): url=%s user=%s", url, username)
                        return "AGE_RESTRICTED"
                    if "login required" in err_str or "requested content is not available" in err_str:
                        logger.warning("⚠️ [DOWNLOAD] Требуется логин/куки (LOGIN_REQUIRED): url=%s user=%s", url, username)
                        return "LOGIN_REQUIRED"
                    logger.error("❌ [DOWNLOAD] yt-dlp ошибка attempt=%s/%s err=%s", attempt, max_attempts, e)
                except Exception:  # noqa: BLE001
                    logger.exception("❌ [DOWNLOAD] Неожиданная ошибка attempt=%s/%s", attempt, max_attempts)
                if attempt < max_attempts:
                    time.sleep(5)
                else:
                    raise Exception("all attempts failed")

        result = await loop.run_in_executor(None, run_download_with_retries)
        if result in ("AGE_RESTRICTED", "LOGIN_REQUIRED"):
            # Возвращаем None в случае, если контент недоступен без авторизации
            return None
        logger.info("✅ [DOWNLOAD] Скачивание завершено: файл=%s", filename)
        return filename