from abc import ABC, abstractmethod


class BaseDownloader(ABC):
    @abstractmethod
    async def download(self, url: str) -> str:
        """Скачать видео по ссылке и вернуть путь к файлу."""
        pass
