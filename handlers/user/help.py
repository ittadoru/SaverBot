from aiogram import types, Router
from aiogram.filters import Command


router = Router()

@router.message(Command("help"))
async def help_handler(message: types.Message):
    print("Help handler вызван")  # или логгер
    help_text = (
        "🤖 Для связи с разработчиком: @ittadorik\n"
        "📢 В будущем будет добавлен чат поддержки прямо в боте."
    )
    await message.answer(help_text)