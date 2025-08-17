import os
import asyncio
from utils import logger as log

async def remove_file_later(path: str, delay: int, message=None):
    """Удаляет файл через указанную задержку (сек)."""
    try:
        await asyncio.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
            log.log_message(f"Файл удалён: {path}", emoji="🗑")
    except Exception as e:
        log.log_error(e, context=f"remove_file_later {path}")
