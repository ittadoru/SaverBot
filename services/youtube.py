"""YouTube downloader с поддержкой проверки размера и агрегированного прогресса.

Исправление: ранее процент "застревал" (например, на ~33%), потому что учитывался
только текущий файл (video или audio). Теперь прогресс агрегирует размеры всех
скачиваемых частей (video + audio) и отображает суммарный процент.
"""

from __future__ import annotations

import os
import uuid
import asyncio
from pytubefix import YouTube
import re 

from utils.logger import get_logger
from .base import BaseDownloader
from config import DOWNLOAD_DIR


logger = get_logger(__name__, platform="youtube")

class YTDLPDownloader(BaseDownloader):
    async def download_by_itag(
        self,
        url: str,
        itag: int,
        message,
        user_id: int | None = None,
    ) -> str | tuple[str, str] | None:
        logger.info("⬇️ [DOWNLOAD] Начало скачивания по itag=%s, url=%s", itag, url)
        """
        Скачивание видео по конкретному itag (mux если нужно).
        """
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        loop = asyncio.get_running_loop()
        yt = YouTube(url)
        stream = yt.streams.get_by_itag(itag)
        if not stream:
            raise Exception(f"No stream found for itag={itag}")
        # Если progressive — просто скачиваем
        if stream.is_progressive:
            def run_download():
                stream.download(output_path=DOWNLOAD_DIR, filename=os.path.basename(filename))
            try:
                await loop.run_in_executor(None, run_download)
            except Exception as e:
                logger.error("❌ [DOWNLOAD] Ошибка при скачивании видео по тегу: %s", str(e))
                return None
            if not os.path.exists(filename):
                return None
            logger.info("✅ [DOWNLOAD] Скачивание успешно: файл=%s", filename)
            return filename
        # Если не progressive — mux video+audio
        else:
            # Скачиваем видео
            video_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}_video.mp4")
            def run_download_video():
                stream.download(output_path=DOWNLOAD_DIR, filename=os.path.basename(video_path))
            await loop.run_in_executor(None, run_download_video)
            # Скачиваем лучший аудиопоток
            audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
            if not audio_stream:
                raise Exception("No audio/mp4 stream found for mux")
            audio_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}_audio.m4a")
            def run_download_audio():
                audio_stream.download(output_path=DOWNLOAD_DIR, filename=os.path.basename(audio_path))
            await loop.run_in_executor(None, run_download_audio)
            # Mux video+audio через ffmpeg
            import subprocess
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "copy",
                filename
            ]

            logger.info(f"🎛️ [MUX] ffmpeg объединение начинается")
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            _stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"❌ [MUX] Ошибка ffmpeg mux: {stderr.decode()}")
                raise Exception(f"ffmpeg mux error: {stderr.decode()}")
            # Удаляем временные файлы
            try:
                await asyncio.to_thread(os.remove, video_path)
                await asyncio.to_thread(os.remove, audio_path)
            except Exception:
                pass
            if not os.path.exists(filename):
                return None
            logger.info("✅ [DOWNLOAD] Скачивание успешно: файл=%s", filename)
            return filename

    async def get_available_video_options(self, url: str) -> dict:
        """
        Возвращает title, thumbnail_url, duration_seconds и список форматов mp4.
        Каждый формат: {'itag', 'res', 'progressive', 'filesize', 'mime_type'}
        """
        loop = asyncio.get_running_loop()
        def fetch():
            yt = YouTube(url)
            title = yt.title
            thumbnail_url = yt.thumbnail_url
            duration_seconds = int(getattr(yt, "length", 0) or 0)
            formats = []
            for s in yt.streams:
                # Только mp4, только видео, 240-2160p
                if s.mime_type and s.mime_type.startswith('video/mp4') and s.resolution:
                    try:
                        res = int(s.resolution.replace('p',''))
                    except Exception:
                        continue
                    if 240 <= res <= 2160:
                        size_mb = s.filesize / 1024 / 1024 if s.filesize else 0
                        formats.append({
                            'itag': s.itag,
                            'res': s.resolution,
                            'progressive': s.is_progressive,
                            'filesize': s.filesize,
                            'mime_type': s.mime_type,
                            'size_mb': round(size_mb, 1)
                        })
            # Сортировка по разрешению (по возрастанию)
            formats.sort(key=lambda x: int(x['res'].replace('p','')))
            return {
                'title': title,
                'thumbnail_url': thumbnail_url,
                'duration_seconds': duration_seconds,
                'formats': formats
            }
        return await loop.run_in_executor(None, fetch)
    

    async def download(self, url: str, message, user_id: int | None = None) -> str | tuple[str, str]:
        logger.info("⬇️ [DOWNLOAD] Начало скачивания лучшего mp4, url=%s", url)
        """
        Скачивание лучшего mp4 (progressive, со звуком) через pytubefix.
        """
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        loop = asyncio.get_running_loop()

        yt = YouTube(url)

        # Лучший mp4 progressive (со звуком) с приоритетом 360p/480p
        stream = None
        for res in ["480p", "360p"]:
            stream = yt.streams.filter(progressive=True, file_extension='mp4', resolution=res).first()
            if stream:
                break
        if not stream:
            # Если нет 360p/480p, берём любой progressive mp4
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()

        if stream:
            def run_download():
                stream.download(output_path=DOWNLOAD_DIR, filename=os.path.basename(filename))

            try:
                await loop.run_in_executor(None, run_download)
            except Exception as e:
                err = str(e)
                logger.error("❌ [DOWNLOAD] Ошибка при скачивании: %s", err)
                return None
            if not os.path.exists(filename):
                return None
            logger.info("✅ [DOWNLOAD] Готово: файл=%s", filename)
            return filename
        else:
            # Нет progressive mp4 — fallback: ищем лучший video/mp4 и audio/mp4, объединяем
            video_stream = None
            for res in ["480p", "360p", "720p"]:
                video_stream = yt.streams.filter(progressive=False, file_extension='mp4', type='video', resolution=res).first()
                if video_stream:
                    break
            if not video_stream:
                video_stream = yt.streams.filter(progressive=False, file_extension='mp4', type='video').order_by('resolution').desc().first()

            audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
            if not video_stream or not audio_stream:
                raise Exception("No suitable video/audio mp4 streams found for mux")
            video_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}_video.mp4")
            audio_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}_audio.m4a")
            def run_download_video():
                video_stream.download(output_path=DOWNLOAD_DIR, filename=os.path.basename(video_path))
            def run_download_audio():
                audio_stream.download(output_path=DOWNLOAD_DIR, filename=os.path.basename(audio_path))
            await loop.run_in_executor(None, run_download_video)
            await loop.run_in_executor(None, run_download_audio)
            # Mux video+audio через ffmpeg
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "copy",
                filename
            ]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            _stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"❌ [MUX] Ошибка ffmpeg mux: {stderr.decode()}")
                raise Exception(f"ffmpeg mux error: {stderr.decode()}")
            # Удаляем временные файлы
            try:
                os.remove(video_path)
                os.remove(audio_path)
            except Exception:
                pass
            if not os.path.exists(filename):
                return None
            logger.info("✅ [MUX] MUX завершён: файл=%s", filename)
            return filename

    async def download_audio(self, url: str) -> str | None:
        logger.info("⬇️ [AUDIO] Начало скачивания аудио, url=%s", url)
        """
        Скачивает лучший аудиопоток (m4a/mp4) через pytubefix, без конвертации в mp3.
        Имя файла — как название видео на YouTube (безопасно для файловой системы).
        """
        yt = YouTube(url)
        safe_title = re.sub(r'[^\w\d\-_ ]', '', yt.title).strip()
        if not safe_title:
            safe_title = str(uuid.uuid4())
        filename = os.path.join(DOWNLOAD_DIR, f"{safe_title}.m4a")
        loop = asyncio.get_running_loop()
        def run_download():
            stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
            if not stream:
                raise Exception("No audio/mp4 stream found")
            stream.download(output_path=DOWNLOAD_DIR, filename=os.path.basename(filename))
        try:
            await loop.run_in_executor(None, run_download)
        except Exception as e:
            logger.error("❌ [AUDIO] Ошибка при скачивании аудио: %s", str(e))
            return None
        if not os.path.exists(filename):
            return None
        logger.info("✅ [AUDIO] Готово: файл=%s", filename)
        return filename
    
