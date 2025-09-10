
"""Webhook сервер FastAPI для обработки уведомлений об оплате и запуска бота."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
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
    add_subscriber_with_duration,
    is_payment_processed,
    mark_payment_processed,
)
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

# ------------------------------- Utilities ----------------------------------
def _calc_expiry(days: int) -> datetime:
    """Возвращает дату окончания (UTC) (8)."""
    return datetime.now(timezone.utc) + timedelta(days=days)

# ------------------------------- Webhook ------------------------------------
@app.post("/yookassa")
async def yookassa_webhook(request: Request) -> JSONResponse:  # (2)
    """Обработка webhook YooKassa (без логирования raw JSON) (1,16)."""
    logger.info("WEBHOOK RAW BODY: %s", await request.json())
    bot: Bot = app.state.bot
    admin_errors: list[str] = []  # (15) агрегируем ошибки
    try:
        data: dict[str, Any] = await request.json()
        logger.info("WEBHOOK RAW BODY: %s", data)
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
        days = 0
        try:
            async with get_session() as session:
                # Повторная проверка idempotency (гонка между процессами)
                if payment_id and await is_payment_processed(session, payment_id):
                    logger.info("🔁 [WEBHOOK] Дубликат (гонка) webhook проигнорирован (payment_id=%s, user_id=%s)", payment_id, user_id)
                    return JSONResponse(content={"status": "ok", "duplicate": True})
                tariff = await get_tariff_by_id(session, tariff_id)
                days = tariff.duration_days  # type: ignore[assignment]
                await add_subscriber_with_duration(session, user_id, days)
                await mark_payment_processed(session, payment_id, user_id)
                await mark_user_has_paid(session, user_id)
                logger.info("✅ [PAYMENT] Подписка продлена: user_id=%s, дней=%s, тариф=%s", user_id, days, tariff_id)
        except Exception as e:  # (6)
            logger.exception("❌ [PAYMENT] Ошибка обработки тарифа/подписки (user_id=%s, tariff_id=%s)", user_id, tariff_id)
            raise HTTPException(status_code=400, detail="Tariff error") from e

        # Уведомления пользователя и группы
        try:
            user = await bot.get_chat(user_id)
            username = f"@{user.username}" if getattr(user, "username", None) else "—"
            full_name = getattr(user, "full_name", None) or getattr(user, "first_name", None) or "—"
            expire_dt = _calc_expiry(days)
            expire_str = expire_dt.strftime('%d.%m.%Y')  # локальный формат (8)

            await bot.send_message(
                user_id,
                (
                    f"✅ Ваша подписка продлена на <b>{days} дней</b>!\n\n"
                    f"🏷️ Тариф: <b>{getattr(tariff, 'name', '—')}</b>\n"
                    f"📅 Действует до (UTC): <b>{expire_str}</b>"
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
                    f"⏳ {days} дн.\n"
                    f"📅 До: {expire_str} (UTC)\n"
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
