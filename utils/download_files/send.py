import os
import asyncio
import logging
from aiogram import Bot, types
from aiogram.types import FSInputFile
from .file_cleanup import remove_file_later
from db.subscribers import is_subscriber as db_is_subscriber
from db.base import get_session
from config import DOMAIN


logger = logging.getLogger(__name__)

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
    Отправка уже скачанного файла:
    - Если превышает технический лимит Telegram (~49 МБ) -> даём ссылку.
    - Иначе отправляем напрямую.
    Бизнес‑лимит (DOWNLOAD_FILE_LIMIT) теперь проверяется ДО скачивания в загрузчиках, чтобы не тратить ресурсы зря.
    """
 
    try:
        me = await bot.get_me()
        # Отправка видео напрямую через Telegram (до 2 ГБ)
        await bot.send_video(
            chat_id=chat_id,
            video=FSInputFile(file_path),
            caption = f"🎬 Скачивай видео с Tiktok | Instagram | YouTube \n\n@{me.username}",      
            width=width,
            height=height,
            supports_streaming=True,
        )
        # Удаляем файл спустя 10 секунд после отправки
        logger.info(f"🗑️ [SEND] Файл {file_path} будет удалён через 10 секунд")
        asyncio.create_task(remove_file_later(file_path, delay=10, message=message))
        logger.info("✅ [SEND] Отправка завершена")
    except Exception as e:
        logger.error(f"❌ [SEND] Ошибка при отправке видео: {e}")
        # Удаляем файл при ошибке
        try:
            await bot.send_message(chat_id, "❗️ Ошибка при отправке видео. Попробуйте позже.")
            await asyncio.to_thread(os.remove, file_path)
        except Exception:
            pass


async def send_audio(bot: Bot, message:types.Message, chat_id: int, file_path: str):
    """
    Отправляет аудио в чат с подписью.
    Файл удаляется через 10 секунд после отправки.
    """
    try:
        logger.info("✉️ [SEND] Отправка audio в Telegram")
        me = await bot.get_me()
        await bot.send_audio(
            chat_id=chat_id,
            audio=FSInputFile(file_path),
            caption = f"🎵 Скачивай аудио с Tiktok | Instagram | YouTube \n\n@{me.username}"
        )
        # Удаляем файл спустя 10 секунд после отправки
        logger.info(f"🗑️ [SEND] Файл {file_path} будет удалён через 10 секунд")
        asyncio.create_task(remove_file_later(file_path, delay=10, message=message))
        logger.info("✅ [SEND] Отправка завершена")
    except Exception as e:
        logger.error(f"❌ [SEND] Ошибка при отправке аудио: {e}")
        try:
            await bot.send_message(chat_id, "❗️ Ошибка при отправке аудио. Попробуйте позже.")
        except Exception:
            pass