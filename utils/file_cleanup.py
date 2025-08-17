import os
import asyncio
import logging

logger = logging.getLogger(__name__)

async def remove_file_later(path: str, delay: int, message=None):
    """Удаляет файл через указанную задержку (сек)."""
    try:
        await asyncio.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
            logger.info("Файл удалён: %s 🗑", path)
    except Exception:
        logger.exception("remove_file_later %s", path)
