from aiogram import types, Router
from aiogram.filters import Command


router = Router()

@router.message(Command("about"))
async def about_handler(message: types.Message):
    about_text = (
        "🤖 Привет! Я — бот, который помогает скачивать видео с популярных платформ:\n"
        "- YouTube\n"
        "- Instagram\n"
        "- TikTok\n\n"
        "🔍 Что я умею:\n"
        "1. Загружать видео в формате до 480p — это позволяет сохранить баланс между качеством и размером файла.\n"
        "2. Если видео весит больше 50 МБ, я не могу отправить его напрямую из-за ограничений Telegram, поэтому высылаю ссылку для скачивания с нашего сервера.\n"
        "3. Все видео на сервере хранятся не более 5 минут.\n\n"
        "Если у вас возникнут вопросы или предложения, не стесняйтесь использовать команду /help для связи с разработчиком."
    )

    await message.answer(about_text)