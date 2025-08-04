from utils.logger import log_error, log_message

def detect_platform(url: str) -> str:
    try:
        # Проверка корректности входного URL
        if not isinstance(url, str) or not url.strip():
            raise ValueError("Пустой или не строковый URL")
        
        # Определяем платформу по подстроке в URL
        if "youtube.com" in url or "youtu.be" in url:
            log_message(f"[DETECT] Обнаружена платформа: YouTube для URL", emoji="🔴")
            return "youtube"
        
        if "vt.tiktok.com" in url or "www.tiktok.com" in url:
            log_message(f"[DETECT] Обнаружена платформа: TikTok для URL", emoji="🔵")
            return "tiktok"
        
        if "www.instagram.com" in url:
            log_message(f"[DETECT] Обнаружена платформа: Instagram для URL", emoji="🟣")
            return "instagram"
        
        # Если не подошло ни одно из условий — платформа неизвестна
        log_message(f"[DETECT] Платформа не определена для URL: {url}", log_level="warning")
        return "unknown"
    except Exception as e:
        # Логируем исключение с контекстом
        log_error(e, context=f"Ошибка определения платформы для URL: {url}")
        return "unknown"
