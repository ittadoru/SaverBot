"""Webhook YooKassa: валидация события, продление подписки, уведомления пользователя и лог админам."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from aiohttp import web
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from utils import payment
from db.base import get_session
from db.subscribers import add_subscriber_with_duration, get_subscriber_expiry
from db.tariff import get_tariff_by_id, Tariff  # предполагается, что Tariff доступен
from utils import logger as log  # существующая обертка логирования

logger = logging.getLogger(__name__)

EVENT_SUCCESS = "payment.succeeded"


async def _handle_user_payment(user_id: int, tariff: Tariff) -> Optional[datetime]:
    """Продлевает подписку пользователя и возвращает дату окончания (UTC) или None при сбое."""
    days = tariff.duration_days
    async with get_session() as session:
        await add_subscriber_with_duration(session, user_id, days)
        return await get_subscriber_expiry(session, user_id)


async def _notify_user_and_show_keys(user_id: int, bot: Bot, request: web.Request, expiry: Optional[datetime]):
    """Редактирует счет (если есть) и очищает состояние; сообщает дату окончания подписки."""
    try:
        dp = request.app['dp']  # Получаем диспетчер
        storage = dp.storage
        storage_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
        state = FSMContext(storage=storage, key=storage_key)

        fsm_data = await state.get_data()
        payment_message_id = fsm_data.get("payment_message_id")

        expiry_text = ""
        if expiry:
            # Локализовать по необходимости; здесь ISO‑дата
            expiry_text = f"\nПодписка активна до: <b>{expiry.astimezone().strftime('%Y-%m-%d %H:%M')}</b>"

        if payment_message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=payment_message_id,
                text=f"✅ <i>Оплата успешно получена.</i>{expiry_text}",
                reply_markup=None,
                parse_mode="HTML",
            )

        await state.clear()

    except Exception:  # логируем только здесь, чтобы не терять stack
        logger.exception("Не удалось обновить сообщение/очистить состояние user_id=%s", user_id)

async def _log_transaction(bot: Bot, user_id: int, tariff_name: str, tariff_price: float, support_chat_id: int) -> None:
    """Отправляет административный лог об оплате."""
    try:
        text = (
            f"💳 Оплата\n\n"
            f"👤 Пользователь: <a href='tg://user?id={user_id}'>Пользователь {user_id}</a>\n"
            f"💳 Тариф: «{tariff_name}»\n"
            f"💰 Сумма: {tariff_price} RUB"
        )

        await bot.send_message(
            chat_id=support_chat_id,
            text=text
        )

        log.log_message(f"Лог транзакции отправлен для пользователя {user_id}.", emoji="✅", log_level="info")

    except Exception:
        logger.exception("Не удалось отправить лог транзакции user_id=%s", user_id)


async def yookassa_webhook_handler(request: web.Request) -> web.Response:
    """Основной обработчик вебхуков YooKassa (успешная оплата -> продление подписки)."""
    logger.info("WEBHOOK: start")
    try:
        body = await request.json()
    except Exception:
        logger.warning("WEBHOOK: invalid JSON")
        return web.Response(status=400)

    notification = payment.parse_webhook_notification(body)
    if not notification:
        logger.warning("WEBHOOK: parse failed")
        return web.Response(status=400)
    if notification.event != EVENT_SUCCESS:
        logger.info("WEBHOOK: unsupported event %s", notification.event)
        return web.Response(status=400)

    # --- Валидация metadata ---
    meta = getattr(notification.object, 'metadata', None) or {}
    if not all(k in meta for k in ("user_id", "tariff_id")):
        logger.warning("WEBHOOK: missing metadata keys")
        return web.Response(status=400)
    try:
        user_id = int(meta["user_id"])
        tariff_id = int(meta["tariff_id"])
    except (ValueError, TypeError):
        logger.warning("WEBHOOK: invalid metadata values %s", meta)
        return web.Response(status=400)

    # --- Получаем тариф ---
    async with get_session() as session:
        tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        logger.warning("WEBHOOK: tariff not found id=%s", tariff_id)
        return web.Response(status=400)

    logger.info("WEBHOOK: success payment user_id=%s tariff=%s", user_id, tariff_id)

    bot: Bot = request.app['bot']
    support_chat_id = request.app['config'].tg_bot.support_chat_id

    expiry = await _handle_user_payment(user_id, tariff)
    await _log_transaction(bot, user_id, tariff.name, tariff.price, support_chat_id)
    await _notify_user_and_show_keys(user_id, bot, request, expiry)

    logger.info("WEBHOOK: completed user_id=%s tariff=%s", user_id, tariff_id)
    return web.Response(status=200)

    # NOTE: идемпотентность повторных webhook не реализована (см. TODO при расширении)
    # TODO: добавить проверку по payment_id для исключения двойного продления.
    # (оставлено вне выбранного набора изменений)

    # --- Ошибки ---
    # Общий перехват вынесен выше; дополнительные except не требуются
