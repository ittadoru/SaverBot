
"""FastAPI webhook server for payments and media file serving."""

from __future__ import annotations

import logging
from json import JSONDecodeError
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from aiogram import Bot
import os
import aiofiles
import asyncio

from db.base import get_session  # (13) убрали динамический импорт
from db.subscribers import (
    is_payment_processed,
    mark_payment_processed,
)
from db.tokens import add_token_x
from db.users import mark_user_has_paid
from db.tariff import get_tariff_by_id
from config import BOT_TOKEN, SUPPORT_GROUP_ID, SUBSCRIBE_TOPIC_ID


logger = logging.getLogger(__name__)

app = FastAPI()

# ------------------------------- Video File Serve ------------------------------------
@app.get("/video/{name}.mp4")
async def serve_video(name: str):
    """Отдаёт mp4-файл из папки downloads по адресу /video/{name}.mp4"""
    file_path = os.path.join("downloads", f"{name}.mp4")
    if not await asyncio.to_thread(os.path.isfile, file_path):
        try:
            async with aiofiles.open("templates/video_not_found.html", encoding="utf-8") as f:
                html = await f.read()
        except Exception:
            html = "<h1>404 Not Found</h1><p>Видео не найдено.</p>"
        return HTMLResponse(content=html, status_code=404)
    
    return FileResponse(file_path, media_type="video/mp4", filename=f"{name}.mp4")

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    if request.url.path.startswith("/video/"):
        try:
            async with aiofiles.open("templates/video_not_found.html", encoding="utf-8") as f:
                html = await f.read()
        except Exception:
            html = "<h1>404 Not Found</h1><p>Видео не найдено.</p>"
    else:
        try:
            async with aiofiles.open("templates/page_not_found.html", encoding="utf-8") as f:
                html = await f.read()
        except Exception:
            html = "<h1>404 Not Found</h1><p>Страница не найдена.</p>"

    return HTMLResponse(content=html, status_code=404)

# ------------------------------- Webhook ------------------------------------
@app.post("/yookassa")
async def yookassa_webhook(request: Request) -> JSONResponse:  # (2)
    """Обработка webhook YooKassa (без логирования raw JSON) (1,16)."""
    bot: Bot = app.state.bot
    try:
        data: dict[str, Any] = await request.json()
        logger.info("🚀 [WEBHOOK] start: %s", data)
    except JSONDecodeError as e:  # (6) узкий except
        logger.error("❌ [WEBHOOK] Некорректный JSON в webhook: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON") from e
    except Exception as e:  # fallback
        logger.exception("❌ [WEBHOOK] Ошибка парсинга JSON в webhook")
        raise HTTPException(status_code=400, detail="Invalid body") from e

    # Извлекаем безопасно нужные поля (6)
    try:
        obj = data["object"]
        payment_status: str = obj["status"]
        metadata = obj["metadata"]
        user_id = int(metadata["user_id"])  # (2)
        tariff_id = int(metadata["tariff_id"])
        payment_id: str = obj.get("id", "")
    except KeyError as e:
        logger.error("❌ [WEBHOOK] Не найден ключ в webhook: %s", e)
        raise HTTPException(status_code=400, detail="Missing key") from e
    except ValueError as e:  # (6) конвертация в int
        logger.error("❌ [WEBHOOK] Некорректное числовое поле в webhook: %s", e)
        raise HTTPException(status_code=400, detail="Bad number") from e

    # Idempotency через БД
    if payment_id:
        async with get_session() as session:
            if await is_payment_processed(session, payment_id):
                logger.info("🔁 [WEBHOOK] Дубликат webhook проигнорирован (payment_id=%s, user_id=%s)", payment_id, user_id)
                return JSONResponse(content={"status": "ok", "duplicate": True})

    if payment_status == "succeeded":  # сохранили прежнюю проверку статуса
        token_x_amount = 0
        try:
            async with get_session() as session:
                # Повторная проверка idempotency (гонка между процессами)
                if payment_id and await is_payment_processed(session, payment_id):
                    logger.info("🔁 [WEBHOOK] Дубликат (гонка) webhook проигнорирован (payment_id=%s, user_id=%s)", payment_id, user_id)
                    return JSONResponse(content={"status": "ok", "duplicate": True})
                tariff = await get_tariff_by_id(session, tariff_id)
                token_x_amount = tariff.duration_days  # type: ignore[assignment]
                snapshot = await add_token_x(session, user_id, token_x_amount)
                await mark_payment_processed(session, payment_id, user_id)
                await mark_user_has_paid(session, user_id)
                await session.commit()
                logger.info(
                    "✅ [PAYMENT] Начислены tokenX: user_id=%s, token_x=%s, тариф=%s",
                    user_id,
                    token_x_amount,
                    tariff_id,
                )
        except Exception as e:  # (6)
            logger.exception("❌ [PAYMENT] Ошибка обработки тарифа/подписки (user_id=%s, tariff_id=%s)", user_id, tariff_id)
            raise HTTPException(status_code=400, detail="Tariff error") from e

        # Уведомления пользователя и группы
        try:
            user = await bot.get_chat(user_id)
            username = f"@{user.username}" if getattr(user, "username", None) else "—"
            full_name = getattr(user, "full_name", None) or getattr(user, "first_name", None) or "—"

            await bot.send_message(
                user_id,
                (
                    f"✅ Оплата прошла успешно!\n\n"
                    f"🏷️ Пакет: <b>{getattr(tariff, 'name', '—')}</b>\n"
                    f"💠 Начислено: <b>+{token_x_amount} tokenX</b>\n"
                    f"💠 Баланс tokenX: <b>{snapshot.token_x}</b>"
                ),
                parse_mode="HTML",
            )
            await bot.send_message(
                SUPPORT_GROUP_ID,
                (
                    f"<b>💳 Новая оплата</b>\n\n"
                    f"👤 {full_name} ({username})\n"
                    f"🆔 <code>{user_id}</code>\n"
                    f"🏷️ {getattr(tariff, 'name', '—')}\n"
                    f"💠 Начислено: +{token_x_amount} tokenX\n"
                    f"💠 Баланс tokenX: {snapshot.token_x}\n"
                ),
                parse_mode="HTML",
                message_thread_id=SUBSCRIBE_TOPIC_ID,
            )
        except Exception as e:  # (6)
            logger.exception("❌ [SEND] Ошибка уведомления пользователя/группы (user_id=%s)", user_id)
            
    return JSONResponse(content={"status": "ok"})

# ------------------------------- Startup ------------------------------------
@app.on_event("startup")
async def on_startup() -> None:  # (2)
    """Инициализация бота."""
    logger.info("🚀 [STARTUP] FastAPI запущен (старт сервера)")
    app.state.bot = Bot(token=BOT_TOKEN)
