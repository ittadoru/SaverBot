from aiogram import Router
from aiogram.types import CallbackQuery
from db.base import get_session
from db.downloads import get_last_links
from utils.keyboards import back_button


router = Router()

@router.callback_query(lambda c: c.data == "download_history")
async def show_download_history(callback: CallbackQuery):
    """Показывает последние 5 скачиваний пользователя."""
    user_id = callback.from_user.id
    async with get_session() as session:
        links = await get_last_links(session, user_id, limit=5)
    if not links:
        text = "У вас пока нет истории скачиваний."
    else:
        text = "<b>🕓 Последние 5 скачиваний:</b>\n" + "\n".join(f"<pre>{url}</pre>" for url in links)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_button("profile"))
    await callback.answer()
