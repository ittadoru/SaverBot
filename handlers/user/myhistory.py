from aiogram.filters import Command
from aiogram import types, Router
from utils.redis import get_user_links

router = Router()

@router.callback_query(lambda c: c.data == "myhistory")
async def show_my_history(message: types.Message):
    user_id = message.from_user.id
    links = await get_user_links(user_id)

    if not links:
        await message.answer("ℹ️ У вас пока нет сохранённых ссылок.")
        return

    # Берём максимум 10 последних ссылок и нумеруем их
    text = "<b>🔗 Ваша история ссылок (последние 10):</b>\n\n"
    for i, link in enumerate(links[:10], start=1):
        text += f"{i}. <pre>{link}</pre>\n"

    await message.answer(text, parse_mode="HTML")
