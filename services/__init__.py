from .youtube.yt_dlp_downloader import YTDLPDownloader
from .tiktok import TikTokDownloader
from .instagram import InstagramDownloader
from utils.platform_detect import detect_platform
from utils import logger as log

def get_downloader(url: str):
    platform = detect_platform(url)
    match platform:
        case "youtube": return YTDLPDownloader()
        case "tiktok": return TikTokDownloader()
        case "instagram": return InstagramDownloader()
        case _: log.log_message("Эта платформа не поддерживается", emoji="⛔️", log_level="error")
