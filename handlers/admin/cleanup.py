import os
from aiogram import Router, F
from aiogram.types import CallbackQuery
from utils import logger as log
from config import DOWNLOAD_DIR

router = Router()


@router.callback_query(F.data == "delete_videos")
async def delete_all_videos(callback: CallbackQuery):
    """Удаление всех видеофайлов из папки downloads (доступ только для админов)."""
    deleted = 0

    if os.path.exists(DOWNLOAD_DIR):
        for filename in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    deleted += 1
                except Exception:
                    pass  # Игнорируем ошибки удаления
    
    log.log_message(f"Удалено {deleted} видеофайлов из папки downloads.", emoji="🗑️")
    await callback.message.answer(f"🗑 Удалено {deleted} файлов из папки downloads.")
    await callback.answer()
