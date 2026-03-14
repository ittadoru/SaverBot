import os
import asyncio
import logging
from aiogram import Bot, types
from aiogram.types import FSInputFile
from .file_cleanup import remove_file_later


logger = logging.getLogger(__name__)
UPLOAD_REQUEST_TIMEOUT_SECONDS = 600
USE_LOCAL_FILE_URI = os.getenv("USE_LOCAL_FILE_URI", "1").strip().lower() in {"1", "true", "yes", "on"}


def _build_local_file_uri(file_path: str) -> str:
    abs_path = os.path.abspath(file_path)
    return f"file://{abs_path}"

async def send_video(
    bot: Bot,
    message: types.Message,
    chat_id: int,
    user_id: int,
    file_path: str,
    width: int,
    height: int,
) -> tuple[bool, str | None]:
    """
    Отправка уже скачанного файла:
    - Отправляем напрямую в Telegram.
    - После отправки файл удаляется отложенно.
    """
 
    try:
        me = await bot.get_me()
        caption = f"🎬 Скачивай видео с Tiktok | Instagram | YouTube \n\n@{me.username}"
        if USE_LOCAL_FILE_URI:
            local_uri = _build_local_file_uri(file_path)
            logger.info("📤 [SEND] Пытаемся отправить видео через local file URI: %s", local_uri)
            try:
                sent_message = await bot.send_video(
                    chat_id=chat_id,
                    video=local_uri,
                    caption=caption,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    request_timeout=UPLOAD_REQUEST_TIMEOUT_SECONDS,
                )
            except Exception as local_err:
                logger.warning("⚠️ [SEND] local file URI не сработал, fallback на FSInputFile: %s", local_err)
                sent_message = await bot.send_video(
                    chat_id=chat_id,
                    video=FSInputFile(file_path),
                    caption=caption,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    request_timeout=UPLOAD_REQUEST_TIMEOUT_SECONDS,
                )
        else:
            sent_message = await bot.send_video(
                chat_id=chat_id,
                video=FSInputFile(file_path),
                caption=caption,
                width=width,
                height=height,
                supports_streaming=True,
                request_timeout=UPLOAD_REQUEST_TIMEOUT_SECONDS,
            )
        file_id = None
        if getattr(sent_message, "video", None):
            file_id = sent_message.video.file_id
        elif getattr(sent_message, "document", None):
            file_id = sent_message.document.file_id
        # Удаляем файл спустя 10 секунд после отправки
        logger.info(f"🗑️ [SEND] Файл {file_path} будет удалён через 10 секунд")
        asyncio.create_task(remove_file_later(file_path, delay=10, message=message))
        logger.info("✅ [SEND] Отправка завершена")
        return True, file_id
    except Exception as e:
        logger.error(f"❌ [SEND] Ошибка при отправке видео: {e}")
        # Удаляем файл при ошибке
        try:
            await bot.send_message(chat_id, "❗️ Ошибка при отправке видео. Попробуйте позже.")
            await asyncio.to_thread(os.remove, file_path)
        except Exception:
            pass
        return False, None


async def send_audio(bot: Bot, message:types.Message, chat_id: int, file_path: str) -> tuple[bool, str | None]:
    """
    Отправляет аудио в чат с подписью.
    Файл удаляется через 10 секунд после отправки.
    """
    try:
        logger.info("✉️ [SEND] Отправка audio в Telegram")
        me = await bot.get_me()
        caption = f"🎵 Скачивай аудио с Tiktok | Instagram | YouTube \n\n@{me.username}"
        if USE_LOCAL_FILE_URI:
            local_uri = _build_local_file_uri(file_path)
            logger.info("📤 [SEND] Пытаемся отправить аудио через local file URI: %s", local_uri)
            try:
                sent_message = await bot.send_audio(
                    chat_id=chat_id,
                    audio=local_uri,
                    caption=caption,
                    request_timeout=UPLOAD_REQUEST_TIMEOUT_SECONDS,
                )
            except Exception as local_err:
                logger.warning("⚠️ [SEND] local file URI для аудио не сработал, fallback на FSInputFile: %s", local_err)
                sent_message = await bot.send_audio(
                    chat_id=chat_id,
                    audio=FSInputFile(file_path),
                    caption=caption,
                    request_timeout=UPLOAD_REQUEST_TIMEOUT_SECONDS,
                )
        else:
            sent_message = await bot.send_audio(
                chat_id=chat_id,
                audio=FSInputFile(file_path),
                caption=caption,
                request_timeout=UPLOAD_REQUEST_TIMEOUT_SECONDS,
            )
        file_id = sent_message.audio.file_id if getattr(sent_message, "audio", None) else None
        # Удаляем файл спустя 10 секунд после отправки
        logger.info(f"🗑️ [SEND] Файл {file_path} будет удалён через 10 секунд")
        asyncio.create_task(remove_file_later(file_path, delay=10, message=message))
        logger.info("✅ [SEND] Отправка завершена")
        return True, file_id
    except Exception as e:
        logger.error(f"❌ [SEND] Ошибка при отправке аудио: {e}")
        try:
            await bot.send_message(chat_id, "❗️ Ошибка при отправке аудио. Попробуйте позже.")
            await asyncio.to_thread(os.remove, file_path)
        except Exception:
            pass
        return False, None
