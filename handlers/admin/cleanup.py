import os
from aiogram import Router, types, F
from config import ADMINS

router = Router()

@router.callback_query(F.data == "delete_videos")
async def delete_all_videos(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.message.answer("⛔️ У вас нет доступа к этой команде.")
        return await callback.answer()
    downloads_dir = os.path.join(os.path.dirname(__file__), '../../downloads')
    deleted = 0
    if os.path.exists(downloads_dir):
        for filename in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    deleted += 1
                except Exception:
                    pass
    await callback.message.answer(f"🗑 Удалено {deleted} файлов из папки downloads.")
    await callback.answer()
