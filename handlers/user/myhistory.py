from aiogram.filters import CommandObject
from aiogram import types, Router
from aiogram.filters import Command
from config import ADMINS
from utils.redis import r, get_user_links

router = Router()

@router.message(Command("myhistory"))
async def show_my_history(message: types.Message):
    user_id = message.from_user.id
    links = await get_user_links(user_id)

    if not links:
        return await message.answer("ℹ️ У вас пока нет ссылок.")

    # Берем максимум 10 ссылок и нумеруем от 1
    text = "<b>🔗 Ваша история ссылок (последние 10):</b>\n\n"
    for link in links[:10]:
        text += f"<pre>{link}</pre>\n"

    await message.answer(text, parse_mode="HTML")

