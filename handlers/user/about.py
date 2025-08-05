from aiogram import types, Router
from aiogram.filters import Command
from .menu import keyboard


router = Router()

@router.callback_query(lambda c: c.data == "more_info")
async def about_handler(callback: types.CallbackQuery):
    """
    Обработчик команды /about.
    Отвечает пользователю информацией о функционале бота.
    """
    about_text = (
        "🤖 Привет! Я — бот, который помогает скачивать видео с популярных платформ:\n"
        "- YouTube\n"
        "- Instagram\n"
        "- TikTok\n\n"
        "🔍 Что я умею:\n"
        "1. Загружать видео в формате до 480p — это позволяет сохранить баланс между качеством и размером файла.\n"
        "2. Если видео весит больше 50 МБ, я не могу отправить его напрямую из-за ограничений Telegram, "
        "поэтому высылаю ссылку для скачивания с нашего сервера.\n"
        "3. Все видео на сервере хранятся не более 5 минут.\n\n"
        "Что бы разблокировать дополнительные функции, такие как скачивание видео в высоком качестве, скачивание аудио и многое другое, введи команту ./subscribe.\n\n"
        "Если у вас возникнут вопросы или предложения, не стесняйтесь использовать команду /help для связи с разработчиком."
    )


    await callback.message.edit_text(about_text, reply_markup=keyboard)
