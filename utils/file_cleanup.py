import os
import aiofiles.os
import asyncio
import logging

logger = logging.getLogger(__name__)

async def remove_file_later(path: str, delay: int, message=None):
    """Удаляет файл через указанную задержку (сек)."""
    try:
        await asyncio.sleep(delay)
        if await asyncio.to_thread(os.path.exists, path):
            await aiofiles.os.remove(path)
            logger.info("🗑️ [DELETE] Файл удалён: %s", path)
    except Exception:
        logger.exception("❌ [DELETE] Ошибка при удалении файла %s", path)
