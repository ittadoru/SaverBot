from aiogram import Router, types, Bot
from aiogram.filters import Command
from utils import redis

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, bot: Bot):
    await redis.add_user(message.from_user, bot)
    username = message.from_user.username or message.from_user.full_name or "пользователь"
    await message.answer(
        f"👋 Привет, {username}!\n\n"
        "Я помогу скачать видео из YouTube, TikTok или Instagram. Просто пришли мне ссылку!\n\n"
        "Твой <b>профиль</b> со статистикой и лимитами всегда доступен через меню или по команде /profile.",
        parse_mode="HTML"
    )
