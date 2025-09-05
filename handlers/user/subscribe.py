from config import SUPPORT_GROUP_ID, SUBSCRIBE_TOPIC_ID
"""Подписка: выбор тарифа и генерация ссылки на оплату."""
import logging
from contextlib import suppress

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError


from db.base import get_session
from db.tariff import get_all_tariffs, get_tariff_by_id
from db.subscribers import add_subscriber_with_duration
import uuid


logger = logging.getLogger(__name__)

router = Router()

BUY_PREFIX = "buy_tariff:"
PARSE_MODE = "HTML"
SUBSCRIBE_HEADER = (
    "<b>💎 Преимущества подписки:</b>\n\n"
    "• 50 скачиваний в сутки\n"
    "• Лимит размера файлов в 7 раз выше\n"
    "• Ссылки на скачивание живут дольше\n"
    "• Нет рекламы\n"
    "• Не требуется подписка на каналы\n"
    "• Доступно любое качество YouTube и аудио\n\n"
    "Выберите вариант подписки:"
)

def _build_tariffs_keyboard(tariffs) -> types.InlineKeyboardMarkup:
    """Строит клавиатуру тарифов с кнопкой назад."""
    builder = InlineKeyboardBuilder()
    # Сортировка тарифов по цене по возрастанию
    for t in sorted(tariffs, key=lambda x: x.price):
        builder.button(
            text=f"{t.name} — {t.price} ⭐️",
            callback_data=f"{BUY_PREFIX}{t.id}"
        )
    builder.button(text="⬅️ В профиль", callback_data="profile")
    builder.adjust(1)
    return builder.as_markup()



@router.callback_query(F.data == "subscribe")
async def subscribe_handler_callback(callback: types.CallbackQuery) -> None:
    await _show_subscribe_menu(callback.message, callback)

@router.message(F.text == "/subscribe")
async def subscribe_handler_command(message: types.Message) -> None:
    await _show_subscribe_menu(message, is_command=True)

async def _show_subscribe_menu(message: types.Message, callback: types.CallbackQuery = None, is_command=False) -> None:
    """Показывает список тарифов или сообщение об их отсутствии."""
    async with get_session() as session:
        tariffs = await get_all_tariffs(session)

    if not tariffs:
        with suppress(TelegramAPIError):
            await message.answer(
                "Пока нет доступных тарифов.",
                parse_mode=PARSE_MODE,
            )
        if callback:
            await callback.answer()
        return

    new_text = SUBSCRIBE_HEADER
    if is_command:
        send = message.answer
    else:
        send = message.edit_text
    with suppress(TelegramAPIError):
        await send(
            new_text,
            reply_markup=_build_tariffs_keyboard(tariffs),
            parse_mode=PARSE_MODE,
        )
    if callback:
        await callback.answer()



@router.callback_query(F.data.startswith(BUY_PREFIX))
async def payment_callback_handler(callback: types.CallbackQuery) -> None:
    """Создаёт платёж и выдаёт кнопку оплаты тарифа."""
    user_id = callback.from_user.id
    raw = callback.data or ""
    try:
        tariff_id = int(raw.removeprefix(BUY_PREFIX))
    except ValueError:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    async with get_session() as session:
        tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    # Генерируем уникальный payload для каждой оплаты
    unique_id = uuid.uuid4().hex
    payload = f"subscribe_{tariff.id}_{user_id}_{unique_id}"
    prices = [types.LabeledPrice(label=tariff.name, amount=int(tariff.price))]
    logger.info(
        "[STARS] send_invoice: user_id=%s, tariff_id=%s, payload=%s, price=%s, label=%s",
        user_id, tariff.id, payload, tariff.price, tariff.name
    )
    await callback.bot.send_invoice(
        chat_id=user_id,
        title=f"Подписка: {tariff.name}",
        description=f"💳 Для оплаты тарифа нажмите на кнопку оплаты",
        payload=payload,
        provider_token="STARS",
        currency="XTR",
        prices=prices,
        need_email=False,
        need_name=False,
        need_phone_number=False,
        is_flexible=False,
    )
    await callback.answer()

@router.message(F.content_type == 'successful_payment')
async def stars_successful_payment_handler(message: types.Message):
    """Обработка успешной оплаты Stars: продлеваем подписку."""
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload  # формат: subscribe_{tariff_id}_{user_id}_{uuid}
    try:
        if payload.startswith("subscribe_"):
            parts = payload.split("_")
            tariff_id = int(parts[1])
        else:
            await message.answer("Ошибка: неизвестный тариф.")
            return
    except Exception:
        await message.answer("Ошибка: не удалось определить тариф.")
        return

    async with get_session() as session:
        tariff = await get_tariff_by_id(session, tariff_id)
        if not tariff:
            await message.answer("Ошибка: тариф не найден.")
            return
        await add_subscriber_with_duration(session, user_id, tariff.duration_days)

    logger.info(
        "[STARS] successful_payment: user_id=%s, payload=%s, total_amount=%s, currency=%s, telegram_payment_charge_id=%s, provider_payment_charge_id=%s",
        user_id,
        payload,
        message.successful_payment.total_amount,
        message.successful_payment.currency,
        message.successful_payment.telegram_payment_charge_id,
        message.successful_payment.provider_payment_charge_id
    )

    await message.answer(
        f"✅ Оплата Stars прошла успешно!\nВаша подписка <b>{tariff.name}</b> активна на {tariff.duration_days} дней.",
        parse_mode="HTML"
    )
    # Уведомление админу/группе
    user = message.from_user
    username = f"@{user.username}" if user.username else "—"
    full_name = user.full_name if hasattr(user, "full_name") else user.first_name
    await message.bot.send_message(
        SUPPORT_GROUP_ID,
        (
            f"<b>💳 Новая оплата через Stars</b>\n\n"
            f"👤 {full_name} ({username})\n"
            f"🆔 <code>{user.id}</code>\n"
            f"🏷️ {tariff.name}\n"
            f"⏳ {tariff.duration_days} дн.\n"
            f"💳 Telegram ID: <code>{message.successful_payment.telegram_payment_charge_id}</code>\n"
            f"💳 Provider ID: <code>{message.successful_payment.provider_payment_charge_id}</code>\n"
        ),
        parse_mode="HTML",
        message_thread_id=SUBSCRIBE_TOPIC_ID,
    )