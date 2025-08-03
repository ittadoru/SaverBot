from .base import BaseDownloader
import yt_dlp
import os
import uuid
from config import DOWNLOAD_DIR
from utils import logger as log

class InstagramDownloader(BaseDownloader):
    async def download(self, url: str) -> str:
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        log.log_download_start(url)

        from utils import yt_dlp_logger as yt

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
                    return  # Успешно
                except yt_dlp.utils.DownloadError as e:
                    log.log_download_error(f"❌ У библиотеки ошибка (попытка {attempt}/{max_attempts}): {e}")
                except Exception as e:
                    log.log_download_error(f"❌ Непредвиденная ошибка (попытка {attempt}/{max_attempts}): {e}")

                if attempt < max_attempts:
                    time.sleep(5)
                else:
                    raise Exception("🚫 Все попытки загрузки не удались")

        await loop.run_in_executor(None, run_download_with_retries)

        log.log_download_complete(filename)
        return filename
