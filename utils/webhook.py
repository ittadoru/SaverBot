from aiohttp import web
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
import payment
from redis_db.subscribers import add_subscriber_with_duration
from redis_db.tariff import get_tariff_by_id
from utils import logger as log  # твоя функция логирования

async def _handle_user_payment(user_id: int, tariff):
    """
    Продлевает подписку пользователя в Redis.
    """
    subscription_days = tariff.duration_days
    await add_subscriber_with_duration(user_id, subscription_days)
    log.log_message(
        f"Подписка пользователя {user_id} продлена на {subscription_days} дней.",
        emoji="🔄", log_level="info"
    )


async def _notify_user_and_show_keys(user_id: int, tariff, bot: Bot, request: web.Request):
    """
    Уведомляет пользователя об успешной оплате и очищает FSM-состояния.
    """
    try:
        dp = request.app['dp']  # Получаем диспетчер
        storage = dp.storage
        storage_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
        state = FSMContext(storage=storage, key=storage_key)

        fsm_data = await state.get_data()
        payment_message_id = fsm_data.get("payment_message_id")

        if payment_message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=payment_message_id,
                text="✅ <i>Этот счет был успешно оплачен.</i>",
                reply_markup=None
            )

        await state.clear()

    except Exception as e:
        log.log_message(
            f"Не удалось очистить состояние или отредактировать сообщение оплаты для пользователя {user_id}: {e}",
            emoji="❌", log_level="error"
        )

async def _log_transaction(bot: Bot, user_id: int, tariff_name: str, tariff_price: float, support_chat_id: int):
    """
    Отправляет в поддержку лог о совершённой оплате.
    """
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

    except Exception as e:
        log.log_message(
            f"Не удалось отправить лог транзакции для пользователя {user_id}: {e}",
            emoji="❌", log_level="error"
        )


async def yookassa_webhook_handler(request: web.Request):
    """
    Обрабатывает вебхуки от YooKassa.
    """
    try:
        request_body = await request.json()
        notification = payment.parse_webhook_notification(request_body)

        if notification is None or notification.event != 'payment.succeeded':
            log.log_message("Получен неверный или неудачный webhook от YooKassa.", emoji="⚠️", log_level="warning")
            return web.Response(status=400)

        metadata = notification.object.metadata
        user_id = int(metadata['user_id'])
        tariff_id = int(metadata['tariff_id'])
        tariff = await get_tariff_by_id(tariff_id)
        log.log_message(f"Получен webhook от пользователя {user_id} с тарифом {tariff_id}.", emoji="🔔", log_level="error")
        if not tariff:
            log.log_message(f"Webhook с несуществующим tariff_id: {tariff_id}", emoji="⚠️", log_level="warning")
            return web.Response(status=400)

        log.log_message(f"Обработка успешной оплаты для пользователя {user_id}, тариф '{tariff.name}'.", emoji="💳", log_level="info")

        bot: Bot = request.app['bot']
        support_chat_id = request.app['config'].tg_bot.support_chat_id

        await _handle_user_payment(user_id, tariff)
        await _log_transaction(bot, user_id, tariff.name, tariff.price, support_chat_id)
        await _notify_user_and_show_keys(user_id, tariff, bot, request)

        return web.Response(status=200)

    except Exception as e:
        log.log_message(f"Фатальная ошибка в обработчике вебхука: {e}", emoji="❌", log_level="error")
        return web.Response(status=500)
