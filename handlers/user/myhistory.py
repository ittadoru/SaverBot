from aiogram import types, Router
from utils.redis import get_user_links
from .menu import keyboard

router = Router()

@router.callback_query(lambda c: c.data == "myhistory")
async def show_my_history(callback: types.CallbackQuery):
    """
    Обработчик нажатия кнопки "Моя история" в меню профиля.
    Показывает последние 10 сохранённых ссылок пользователя.
    """
    user_id = callback.from_user.id
    links = await get_user_links(user_id)

    if not links:
        await callback.message.edit_text("ℹ️ У вас пока нет сохранённых ссылок.")
        return

    # Берём максимум 10 последних ссылок и нумеруем их
    text = "<b>🔗 Ваша история ссылок (последние 10):</b>\n\n"
    for link in links[-10:]:
        text += f"<pre>{link}</pre>\n"

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
