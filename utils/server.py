import asyncio
import os
import traceback

from fastapi import FastAPI
from fastapi.responses import FileResponse
from aiogram import types

from utils import logger as log
from config import ADMIN_ERROR


app = FastAPI()


@app.get("/video/{filename}")
async def download_video(filename: str):
    """
    Обработка HTTP GET запроса для скачивания видео по имени файла.
    Возвращает видеофайл из папки downloads.
    """
    filepath = f"downloads/{filename}"

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="video/mp4",
    )


async def remove_file_later(path: str, delay: int, message: types.Message):
    """
    Асинхронно удаляет файл спустя delay секунд.
    При ошибке удаления логирует ошибку и отправляет сообщение администратору.
    """
    log.log_message(
        f"[CLEANUP] Планируется удаление через {delay} секунд: {path}", emoji="⏳"
    )
    await asyncio.sleep(delay)
    try:
        os.remove(path)
        log.log_cleanup_video(path)
    except Exception as e:
        error_text = f"Ошибка: {e}"
        full_trace = traceback.format_exc()
        log.log_error(error_text)
        log.log_error(full_trace)

        # Отправка сообщения админу об ошибке удаления файла
        try:
            await message.bot.send_message(
                ADMIN_ERROR,
                f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                parse_mode="HTML",
            )
        except Exception as send_err:
            log.log_error(f"Не удалось отправить ошибку админу: {send_err}")
