import asyncio
import os
import traceback
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from aiogram import types, Bot

from utils import redis, logger as log
from config import ADMIN_ERROR, BOT_TOKEN
from fastapi.templating import Jinja2Templates
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app = FastAPI()

class BotLogHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        log.log_message(msg)  # или log.log_error(msg) для ошибок

# Перехват стандартных логов FastAPI/Uvicorn
logging.getLogger("uvicorn.access").handlers = [BotLogHandler()]
logging.getLogger("uvicorn.error").handlers = [BotLogHandler()]
logging.getLogger("fastapi").handlers = [BotLogHandler()]

@app.post("/yookassa")
async def yookassa_webhook(request: Request):
    """
    Обрабатывает вебхуки от YooKassa.
    При успешной оплате начисляет дни подписки пользователю.
    """
    bot: Bot = app.state.bot
    r = app.state.redis

    try:
        data = await request.json()
    except Exception as e:
        log.log_message(f"Ошибка парсинга JSON: {e}", log_level="error", emoji="⚠️")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Корректная обработка webhook: начисляем дни по тарифу, а не по сумме оплаты
    try:
        payment_status = data["object"]["status"]
        user_id_str = data["object"]["metadata"]["user_id"]
        tariff_id_str = data["object"]["metadata"]["tariff_id"]

        user_id = int(user_id_str)
        tariff_id = int(tariff_id_str)
    except (KeyError, ValueError) as e:
        log.log_message(f"Ошибка данных webhook: {e}", log_level="error", emoji="❌")
        raise HTTPException(status_code=400, detail="Invalid data")

    if payment_status == "succeeded":
        try:
            tariff = await redis.get_tariff_by_id(tariff_id)
            days = tariff.duration_days
        except Exception as e:
            log.log_message(f"Ошибка получения тарифа: {e}", log_level="error", emoji="❌")
            raise HTTPException(status_code=400, detail="Tariff error")

        await redis.add_subscriber_with_duration(user_id, days)
        log.log_message(f"Подписка продлена для user_id={user_id} на {days} дней", emoji="✅")

        try:
            await bot.send_message(
                user_id,
                f"✅ Ваша подписка успешно оформлена и продлена на {days} дней!"
            )
        except Exception as e:
            log.log_message(f"Ошибка отправки сообщения пользователю: {e}", log_level="error", emoji="⚠️")

    return JSONResponse(content={"status": "ok"})


@app.get("/video/{filename}")
async def download_video(request: Request, filename: str):
    """
    Обработка HTTP GET запроса для скачивания видео по имени файла.
    Возвращает видеофайл из папки downloads.
    """
    filepath = f"downloads/{filename}"
    if not os.path.exists(filepath):
        log.log_message(f"Файл не найден: {filepath}", log_level="error", emoji="❌")
        return templates.TemplateResponse(
            "video_not_found.html",
            {"request": request},
            status_code=404
        )
    log.log_message(f"Запрос на скачивание файла: {filepath}", emoji="📥")
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



@app.on_event("startup")
async def on_startup():
    """
    Инициализация бота и Redis при запуске FastAPI-приложения.
    """
    log.log_message("Запуск FastAPI приложения", emoji="🚀")
    app.state.bot = Bot(token=BOT_TOKEN)
    app.state.redis = redis