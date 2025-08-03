
import os
from utils import logger as log
from aiogram import Bot, types
from aiogram.types import FSInputFile
import asyncio

from utils.redis import is_subscriber
from utils.server import remove_file_later

async def send_video(bot: Bot, chat_id: int, user_id: int, file_path: str, width: int, height: int):
    log.log_send_start(chat_id)

    if os.path.getsize(file_path) > 49 * 1024 * 1024:
        file_name = os.path.basename(file_path)
        link = f"http://127.0.0.1:8000/video/{file_name}"
        await bot.send_message(chat_id, text=f"📥 Ваша одноразовая ссылка для скачивания видео готово: {link}\n\n@savetokgrambot")
        if is_subscriber(user_id):
            asyncio.create_task(remove_file_later(file_path, delay=3600))
        else:
            asyncio.create_task(remove_file_later(file_path, delay=300))

    else:
        await bot.send_video(
            caption="💾 Скачивай видео с YouTube | Instagram | Tiktok \n\n@savetokgrambot",
            chat_id=chat_id,
            video=FSInputFile(file_path),
            width=width,
            height=height,
            supports_streaming=True,
        )
        # Можно удалить файл после отправки
        asyncio.create_task(remove_file_later(file_path, delay=10))


    log.log_send_complete()


async def send_audio(bot: Bot, chat_id: int, file_path: str):
    log.log_send_start(chat_id)
    from aiogram.types import FSInputFile
    await bot.send_audio(
        chat_id=chat_id,
        audio=FSInputFile(file_path),
        caption="💾 Аудио из YouTube | @savetokgrambot"
    )
    # Можно удалить файл после отправки
    import asyncio
    asyncio.create_task(remove_file_later(file_path, delay=10))
    log.log_send_complete()