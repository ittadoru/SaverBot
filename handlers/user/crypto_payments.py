import logging

from aiogram.types import Message
from aiosend.types import Invoice

from db.base import get_session
from db.subscribers import add_subscriber_with_duration
from db.tariff import get_tariff_by_id
from db.users import get_user_by_id, mark_user_has_paid
from config import SUBSCRIBE_TOPIC_ID, SUPPORT_GROUP_ID
from loader import crypto_pay, bot

logger = logging.getLogger(__name__)


@crypto_pay.invoice_paid()
async def crypto_payment_handler(invoice: Invoice, message: Message):
    """
    Handles successful crypto payments.
    """
    logger.info(f"Received crypto payment: {invoice.invoice_id}")
    if not invoice.payload:
        logger.warning(f"Crypto payment {invoice.invoice_id} has no payload.")
        return

    try:
        user_id, tariff_id = map(int, invoice.payload.split(':'))
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing payload for crypto payment {invoice.invoice_id}: {e}")
        await message.answer("Произошла ошибка при обработке вашего платежа. Пожалуйста, свяжитесь с поддержкой.")
        return

    async with get_session() as session:
        user = await get_user_by_id(session, user_id)
        tariff = await get_tariff_by_id(session, tariff_id)

        if not user or not tariff:
            logger.error(f"User ({user_id}) or Tariff ({tariff_id}) not found for crypto payment {invoice.invoice_id}.")
            await message.answer("Не удалось найти информацию о пользователе или тарифе. Обратитесь в поддержку.")
            return

        subscriber = await add_subscriber_with_duration(session, user_id, tariff.duration_days)
        await mark_user_has_paid(session, user_id)

        # Notify user
        await message.answer(
            (f"✅ Оплата криптой успешно получена!\n\n"
            f"🏷️ Тариф: <b>{tariff.name}</b>\n"
            f"⏳ Дней: <b>{tariff.duration_days}</b>\n"
            f"📅 Подписка до: <b>{subscriber.expire_at.strftime('%d.%m.%Y')}</b>")
        )

        # Notify admin
        await bot.send_message(
            SUPPORT_GROUP_ID,
            (f"💸 <b>Оплата криптой</b>\n\n"
            f"👤 Пользователь: {user.first_name} ({user.username})\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"🏷️ Тариф: <b>{tariff.name}</b>\n"
            f"💰 Сумма: <b>{invoice.amount} {invoice.asset}</b>\n"
            f"⏳ Дней: <b>{tariff.duration_days}</b>\n"
            f"📅 Подписка до: <b>{subscriber.expire_at.strftime('%d.%m.%Y')}</b>"),
            message_thread_id=SUBSCRIBE_TOPIC_ID
        )
    logger.info(f"Successfully processed crypto payment {invoice.invoice_id} for user {user_id}")
