import asyncio
import os
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from aiogram import types, Bot

from utils import redis, logger as log
from config import ADMIN_ERROR, BOT_TOKEN


app = FastAPI()


@app.post("/yookassa")
async def yookassa_webhook(request: Request):
    bot: Bot = app.state.bot
    r = app.state.redis

    try:
        data = await request.json()
    except Exception as e:
        log.log_message(f"Ошибка парсинга JSON: {e}", log_level="error", emoji="⚠️")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    log.log_message(f"Получен webhook: {data}", emoji="🔔")

    # Пример проверки платежа (как в твоём aiohttp варианте)
    try:
        payment_id = data["object"]["id"]
        payment_status = data["object"]["status"]
        amount_str = data["object"]["amount"]["value"]
        user_id_str = data["object"]["metadata"]["user_id"]

        amount = int(float(amount_str))  # "49.00" -> 49.0 -> 49
        user_id = int(user_id_str)       # "1204967278" -> 1204967278
    except (KeyError, ValueError) as e:
        log.log_message(f"Ошибка данных webhook: {e}", log_level="error", emoji="❌")
        raise HTTPException(status_code=400, detail="Invalid data")

    if payment_status == "succeeded":
        # Продление подписки
        days = amount  # если сумма равна количеству дней, как у тебя
        await redis.add_subscriber_with_duration(user_id, days)
        log.log_message(f"Подписка продлена для user_id={user_id} на {days} дней", emoji="✅")

        # Отправка сообщения пользователю
        try:
            await bot.send_message(
                user_id,
                f"✅ Ваша подписка успешно оформлена и продлена на {days} дней!"
            )
        except Exception as e:
            log.log_message(f"Ошибка отправки сообщения пользователю: {e}", log_level="error", emoji="⚠️")

    return JSONResponse(content={"status": "ok"})


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



@app.on_event("startup")
async def on_startup():
    """
    Инициализация бота и Redis при запуске FastAPI-приложения.
    """
    app.state.bot = Bot(token=BOT_TOKEN)
    app.state.redis = redis