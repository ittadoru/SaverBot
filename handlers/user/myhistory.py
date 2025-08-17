from aiogram import Router
from aiogram.types import CallbackQuery
from db.base import get_session
from db.downloads import get_last_links

router = Router()

@router.callback_query(lambda c: c.data == "download_history")
async def show_download_history(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with get_session() as session:
        links = await get_last_links(session, user_id, limit=10)
    if not links:
        text = "У вас пока нет истории скачиваний."
    else:
        text = "<b>🕓 Последние 10 скачиваний:</b>\n" + "\n".join(f"<pre>{url}</pre>" for i, url in enumerate(links))
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
