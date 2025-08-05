from utils.logger import log_error, log_message

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
        
        log_message(f"[DETECT] Платформа не определена для URL: {url}", log_level="warning")
        return "unknown"
    except Exception as e:
        log_error(e, context=f"Ошибка определения платформы для URL: {url}")
        return "unknown"
