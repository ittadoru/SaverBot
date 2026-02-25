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
    async def download(self, url: str, message=None, user_id: int | None = None) -> str | None:
        """Загрузка видео с Instagram через yt-dlp.

        Возвращает путь к файлу при успехе и None, если контент недоступен
        (например, требуется авторизация/cookies или пост приватный).
        """
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        logger.info("⬇️ [DOWNLOAD] Начало скачивания: url=%s", url)
        loop = asyncio.get_running_loop()

        # Поддержка cookies / логина через переменные окружения
        cookies_path = (os.environ.get("COOKIES_PATH") or "").strip()
        insta_username = (os.environ.get("INSTAGRAM_USERNAME") or "").strip()
        insta_password = (os.environ.get("INSTAGRAM_PASSWORD") or "").strip()

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

        # Если задан файл cookies — передаём в yt-dlp
        if cookies_path:
            if os.path.isfile(cookies_path):
                ydl_opts["cookiefile"] = cookies_path
            else:
                logger.warning("⚠️ [DOWNLOAD] COOKIES_PATH не найден: %s", cookies_path)
        # Если заданы учётные данные — передаём их
        if insta_username and insta_password:
            ydl_opts["username"] = insta_username
            ydl_opts["password"] = insta_password

        def classify_download_error(err_str: str) -> str:
            if any(x in err_str for x in ("18 years old", "age-restricted", "restricted video")):
                return "AGE_RESTRICTED"
            if any(
                x in err_str
                for x in (
                    "login required",
                    "requested content is not available",
                    "instagram sent an empty media response",
                    "check if this post is accessible in your browser without being logged-in",
                    "api is not granting access",
                    "cookies",
                    "private",
                )
            ):
                return "LOGIN_REQUIRED"
            return "RETRY"

        def run_download_with_retries():
            max_attempts = 3
            username = None
            if hasattr(message, "from_user") and getattr(message.from_user, "username", None):
                username = message.from_user.username
            elif hasattr(message, "username"):
                username = getattr(message, "username", None)
            elif isinstance(message, int):
                username = f"user_id={message}"
            elif isinstance(user_id, int):
                username = f"user_id={user_id}"

            for attempt in range(1, max_attempts + 1):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    return "OK"
                except yt_dlp.utils.DownloadError as e:  # noqa: PERF203
                    err_str = str(e).lower()
                    status = classify_download_error(err_str)
                    if status == "AGE_RESTRICTED":
                        logger.warning(
                            "⚠️ [DOWNLOAD] Ограничение по возрасту (AGE_RESTRICTED): url=%s user=%s",
                            url,
                            username,
                        )
                        return status
                    if status == "LOGIN_REQUIRED":
                        logger.warning(
                            "⚠️ [DOWNLOAD] Требуется логин/куки (LOGIN_REQUIRED): url=%s user=%s",
                            url,
                            username,
                        )
                        return status
                    logger.error("❌ [DOWNLOAD] yt-dlp ошибка attempt=%s/%s err=%s", attempt, max_attempts, e)
                except Exception:  # noqa: BLE001
                    logger.exception("❌ [DOWNLOAD] Неожиданная ошибка attempt=%s/%s", attempt, max_attempts)
                if attempt < max_attempts:
                    time.sleep(5)
            return "FAILED"

        result = await loop.run_in_executor(None, run_download_with_retries)
        if result != "OK":
            logger.warning("⚠️ [DOWNLOAD] Скачивание не выполнено: status=%s url=%s", result, url)
            # Возвращаем None в случае, если контент недоступен без авторизации
            return None
        logger.info("✅ [DOWNLOAD] Скачивание завершено: файл=%s", filename)
        return filename
