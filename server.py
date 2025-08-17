"""Webhook сервер FastAPI для обработки уведомлений об оплате и запуска бота."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from aiogram import Bot

from db.base import get_session  # (13) убрали динамический импорт
from db.subscribers import (
    add_subscriber_with_duration,
    is_payment_processed,
    mark_payment_processed,
)
from db.users import mark_user_has_paid
from db.tariff import get_tariff_by_id
from config import BOT_TOKEN, SUPPORT_GROUP_ID, SUBSCRIBE_TOPIC_ID, PRIMARY_ADMIN_ID

logger = logging.getLogger(__name__)  # (12) стандартный логгер вместо custom wrapper

app = FastAPI()


# ---------------------------- Логирование Uvicorn ---------------------------
class BotLogHandler(logging.Handler):  # type: ignore[misc]
    """Handler, перенаправляющий логи в Telegram через существующий механизм."""

    def emit(self, record: logging.LogRecord) -> None:  # (2) типизация
        try:
            from utils import logger as tg_log  # локальный импорт чтобы избежать циклов
            msg = self.format(record)
            tg_log.info(msg)
        except Exception:  # noqa: BLE001 - не роняем из-за handler
            pass


logging.getLogger("uvicorn.access").handlers = [BotLogHandler()]
logging.getLogger("uvicorn.error").handlers = [BotLogHandler()]
logging.getLogger("fastapi").handlers = [BotLogHandler()]


# Idempotency теперь в БД (processed_payments)


# ------------------------------- Utilities ----------------------------------
def _calc_expiry(days: int) -> datetime:
    """Возвращает дату окончания (UTC) (8)."""
    return datetime.now(timezone.utc) + timedelta(days=days)


# ------------------------------- Webhook ------------------------------------
@app.post("/yookassa")
async def yookassa_webhook(request: Request) -> JSONResponse:  # (2)
    """Обработка webhook YooKassa (без логирования raw JSON) (1,16)."""
    bot: Bot = app.state.bot
    admin_errors: list[str] = []  # (15) агрегируем ошибки

    try:
        data: dict[str, Any] = await request.json()
    except JSONDecodeError as e:  # (6) узкий except
        logger.error("Invalid JSON: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON") from e
    except Exception as e:  # fallback
        logger.exception("JSON parse failure")
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
        logger.error("Missing key in webhook: %s", e)
        raise HTTPException(status_code=400, detail="Missing key") from e
    except ValueError as e:  # (6) конвертация в int
        logger.error("Invalid int field: %s", e)
        raise HTTPException(status_code=400, detail="Bad number") from e

    # Idempotency через БД
    if payment_id:
        async with get_session() as session:
            if await is_payment_processed(session, payment_id):
                logger.info("Duplicate webhook ignored payment_id=%s user_id=%s", payment_id, user_id)
                return JSONResponse(content={"status": "ok", "duplicate": True})

    if payment_status == "succeeded":  # сохранили прежнюю проверку статуса
        days = 0
        try:
            async with get_session() as session:
                # Повторная проверка idempotency (гонка между процессами)
                if payment_id and await is_payment_processed(session, payment_id):
                    logger.info("Duplicate (race) webhook ignored payment_id=%s user_id=%s", payment_id, user_id)
                    return JSONResponse(content={"status": "ok", "duplicate": True})
                tariff = await get_tariff_by_id(session, tariff_id)
                days = tariff.duration_days  # type: ignore[assignment]
                await add_subscriber_with_duration(session, user_id, days)
                await mark_payment_processed(session, payment_id, user_id)
                await mark_user_has_paid(session, user_id)
                logger.info("Subscription extended user_id=%s days=%s tariff_id=%s", user_id, days, tariff_id)
        except Exception as e:  # (6)
            admin_errors.append(f"Tariff/subscription error: {e}")
            logger.exception("Tariff handling failed user_id=%s tariff_id=%s", user_id, tariff_id)
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
            admin_errors.append(f"Notify error: {e}")
            logger.exception("User/group notify failed user_id=%s", user_id)

    # (15) Одно агрегированное сообщение админу при наличии ошибок
    if admin_errors:
        try:
            await bot.send_message(PRIMARY_ADMIN_ID, "\n".join(admin_errors))
        except Exception:  # noqa: BLE001
            logger.warning("Failed to send admin aggregated error")

    return JSONResponse(content={"status": "ok"})


# ------------------------------- Startup ------------------------------------
@app.on_event("startup")
async def on_startup() -> None:  # (2)
    """Инициализация бота."""
    logger.info("FastAPI startup")
    app.state.bot = Bot(token=BOT_TOKEN)
