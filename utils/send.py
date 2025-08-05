import os
import asyncio

from aiogram import Bot, types
from aiogram.types import FSInputFile

from utils import logger as log
from utils.redis import is_subscriber
from utils.server import remove_file_later

from config import DOMAIN

async def send_video(
    bot: Bot,
    message: types.Message,
    chat_id: int,
    user_id: int,
    file_path: str,
    width: int,
    height: int,
):
    """
    Отправляет видео в чат. Если файл больше 49 МБ, отправляет ссылку на скачивание.
    Для подписчиков ссылка удаляется через 1 час, для остальных — через 5 минут.
    Для маленьких файлов видео отправляется напрямую с последующим удалением файла.
    """
    log.log_send_start(chat_id)

    if os.path.getsize(file_path) > 49 * 1024 * 1024:
        file_name = os.path.basename(file_path)
        link = f"http://{DOMAIN}/video/{file_name}"

        await bot.send_message(
            chat_id,
            text=f"📥 Ваша одноразовая ссылка для скачивания видео готово: {link}\n\n@savetokgrambot",
        )

        if await is_subscriber(user_id):
            asyncio.create_task(remove_file_later(file_path, delay=1800, message=message))
        else:
            asyncio.create_task(remove_file_later(file_path, delay=300, message=message))

    else:
        # Отправка видео напрямую через Telegram
        await bot.send_video(
            chat_id=chat_id,
            video=FSInputFile(file_path),
            caption="💾 Скачивай видео с YouTube | Instagram | Tiktok \n\n@savetokgrambot",
            width=width,
            height=height,
            supports_streaming=True,
        )

        # Удаляем файл спустя 10 секунд после отправки
        asyncio.create_task(remove_file_later(file_path, delay=10, message=message))

    log.log_send_complete()


async def send_audio(bot: Bot, message:types.Message, chat_id: int, file_path: str):
    """
    Отправляет аудио в чат с подписью.
    Файл удаляется через 10 секунд после отправки.
    """
    log.log_send_start(chat_id)

    await bot.send_audio(
        chat_id=chat_id,
        audio=FSInputFile(file_path),
        caption="💾 Аудио из YouTube | @savetokgrambot",
    )

    # Удаляем файл спустя 10 секунд после отправки
    asyncio.create_task(remove_file_later(file_path, delay=10, message=message))

    log.log_send_complete()
