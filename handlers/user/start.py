from aiogram import Router, types, Bot
from aiogram.filters import Command

from utils import redis


router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, bot: Bot):
    await redis.add_user(message.from_user, bot)
    await message.answer("👋 Привет! Отправь мне ссылку на видео из YouTube, TikTok или Instagram.")
