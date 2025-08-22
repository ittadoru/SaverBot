import logging

logger = logging.getLogger(__name__)

def detect_platform(url: str) -> str:
    try:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("Пустой или не строковый URL")

        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"

        if "vt.tiktok.com" in url or "www.tiktok.com" in url:
            return "tiktok"

        if "www.instagram.com" in url:
            return "instagram"

        logger.warning("⚠️ [DETECT] Платформа не определена для URL: %s", url)
        return "unknown"
    except Exception as e:
        logger.exception("❌ [EXCEPTION] Ошибка определения платформы для URL: %s", url)
        return "unknown"
