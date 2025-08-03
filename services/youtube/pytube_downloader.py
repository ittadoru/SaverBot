from pytube import YouTube
import os
import uuid
from config import DOWNLOAD_DIR

class PyTubeDownloader:
    async def download(self, url: str, resolution: str = "480") -> str:
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension='mp4', res=f"{resolution}p").first()
        if not stream:
            raise Exception("Не найден подходящий поток через pytube")
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        stream.download(output_path=DOWNLOAD_DIR, filename=filename)
        return filename

    async def download_audio(self, url: str) -> str:
        yt = YouTube(url)
        stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()
        if not stream:
            raise Exception("Не найден аудио поток через pytube")
        filename = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp3")
        stream.download(output_path=DOWNLOAD_DIR, filename=filename)
        return filename
