from config import SUPPORT_GROUP_ID, SUBSCRIBE_TOPIC_ID
"""Store: choose tokenX package and generate payment links."""
import logging
from contextlib import suppress

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError


from db.base import get_session
from db.tariff import get_all_tariffs, get_tariff_by_id
from db.tokens import add_token_x
from db.users import mark_user_has_paid
import uuid
from loader import crypto_pay
from utils.currency import rub_to_usdt


logger = logging.getLogger(__name__)

router = Router()

BUY_PREFIX = "buy_tariff:"
PARSE_MODE = "HTML"
SUBSCRIBE_HEADER = (
    "<b>🛒 Магазин tokenX</b>\n\n"
    "tokenX используются для высокого качества YouTube и сброса лимита Tiktok/Insta.\n\n"
    "Выберите пакет:"
)

def _build_tariffs_keyboard(tariffs) -> types.InlineKeyboardMarkup:
    """Строит клавиатуру тарифов с кнопкой назад."""
    builder = InlineKeyboardBuilder()
    # Сортировка тарифов по цене по возрастанию
    for t in sorted(tariffs, key=lambda x: x.price):
        builder.button(
            text=(
                f"{t.name} — +{t.duration_days} tokenX "
                f"({getattr(t, 'price', t.price)} RUB / {getattr(t, 'star_price', t.price)}⭐️)"
            ),
            callback_data=f"{BUY_PREFIX}{t.id}"
        )
    builder.button(text="⬅️ В профиль", callback_data="start")
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
    """Показывает способы оплаты пакета tokenX."""
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

    # Показываем выбор способа оплаты пакета tokenX
    builder = InlineKeyboardBuilder()
    # builder.button(
    #     text=f"💳 Оплатить {tariff.price} RUB",
    #     callback_data=f"pay_yookassa:{tariff.id}"
    # )
    builder.button(
        text=f"⭐️ Оплатить звездами", callback_data=f"pay_stars:{tariff.id}")
    builder.button(text="💎 Оплатить криптой", callback_data=f"pay_crypto:{tariff.id}")
    builder.button(text="⬅️ Назад", callback_data="subscribe")
    builder.adjust(1)
    await callback.message.edit_text(
        f"<b>Выберите способ оплаты пакета <u>{tariff.name}</u></b>\n"
        f"<b>Начисление:</b> +{tariff.duration_days} tokenX\n\n",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Новый handler для оплаты через Stars
@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars_callback_handler(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    try:
        tariff_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("Ошибка тарифа", show_alert=True)
        return

    async with get_session() as session:
        tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    # Генерируем уникальный payload для каждой оплаты
    unique_id = uuid.uuid4().hex
    payload = f"subscribe_{tariff.id}_{user_id}_{unique_id}"
    prices = [types.LabeledPrice(label=tariff.name, amount=int(getattr(tariff, 'star_price', tariff.price)))]
    logger.info(
        "[STARS] send_invoice: user_id=%s, tariff_id=%s, payload=%s, star_price=%s, label=%s",
        user_id, tariff.id, payload, getattr(tariff, 'star_price', tariff.price), tariff.name
    )
    await callback.bot.send_invoice(
        chat_id=user_id,
        title=f"Пакет tokenX: {tariff.name}",
        description=f"💳 Оплата пакета +{tariff.duration_days} tokenX",
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

@router.callback_query(F.data.startswith("pay_yookassa:"))
async def pay_yookassa_callback_handler(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    try:
        tariff_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("Ошибка тарифа", show_alert=True)
        return

    async with get_session() as session:
        tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    try:
        from utils.payment import create_payment
        me = await callback.bot.get_me()
        payment_url, payment_id = create_payment(
            user_id=user_id,
            amount=tariff.price,
            description=f"Пакет tokenX: {tariff.name}",
            bot_username=me.username or "bot",
            metadata={
                "user_id": str(user_id),
                "tariff_id": str(tariff.id)
            }
        )
    except Exception as e:
        logger.exception("Ошибка создания платежа YooKassa")
        await callback.answer("Ошибка создания платежа", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Перейти к оплате", url=payment_url)
    builder.button(text="⬅️ Назад", callback_data="subscribe")
    builder.adjust(1)
    await callback.message.edit_text(
        f"<b>Оплата пакета <u>{tariff.name}</u> через YooKassa</b>\n\n" +
        f"Начисление: <b>+{tariff.duration_days} tokenX</b>\n" +
        f"Сумма: <b>{tariff.price}₽</b>\n\n" +
        "Нажмите кнопку ниже для перехода к оплате.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@router.message(F.content_type == 'successful_payment')
async def stars_successful_payment_handler(message: types.Message) -> None:
    """Обработка успешной оплаты Stars: начисляем tokenX."""
    payment = message.successful_payment
    user_id = message.from_user.id
    payload = payment.invoice_payload  # формат: subscribe_{tariff_id}_{user_id}_{uuid}
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
        await add_token_x(session, user_id, tariff.duration_days)
        await mark_user_has_paid(session, user_id)
        await session.commit()

    logger.info(
        "[STARS] successful_payment: user_id=%s, payload=%s, total_amount=%s, currency=%s, telegram_payment_charge_id=%s, provider_payment_charge_id=%s",
        user_id,
        payload,
        payment.total_amount,
        payment.currency,
        payment.telegram_payment_charge_id,
        payment.provider_payment_charge_id
    )

    await message.answer(
        (
            "✅ Оплата Stars прошла успешно!\n"
            f"Начислено: <b>+{tariff.duration_days} tokenX</b>\n"
            f"Пакет: <b>{tariff.name}</b>."
        ),
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
            f"💠 Начислено: +{tariff.duration_days} tokenX\n"
            f"💳 Telegram ID: <code>{payment.telegram_payment_charge_id}</code>\n"
            f"💳 Provider ID: <code>{payment.provider_payment_charge_id}</code>\n"
        ),
        parse_mode="HTML",
        message_thread_id=SUBSCRIBE_TOPIC_ID,
    )


@router.callback_query(F.data.startswith("pay_crypto:"))
async def pay_crypto_callback_handler(callback: types.CallbackQuery) -> None:
    """Создаёт крипто-инвойс через CryptoBot и отправляет ссылку на оплату."""
    user_id = callback.from_user.id
    try:
        tariff_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("Ошибка тарифа", show_alert=True)
        return

    async with get_session() as session:
        tariff = await get_tariff_by_id(session, tariff_id)
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    # Конвертируем рубли в USDT (минимум 1 USDT)
    usdt_amount = await rub_to_usdt(tariff.price)

    if usdt_amount is None:
        logger.error("❌ [SUBSCRIBE] Не удалось получить курс для конвертации в USDT для user=%s", user_id)
        await callback.message.answer("Не удалось получить актуальный курс валют. Пожалуйста, попробуйте позже.")
        await callback.answer()
        return

    try:
        invoice = await crypto_pay.create_invoice(
            asset="USDT",
            amount=usdt_amount,
            description=f"Saver: {tariff.name}",
            payload=f"{user_id}:{tariff_id}"
        )
        pay_url = invoice.bot_invoice_url
        invoice.poll(message=callback.message)
    except Exception as e:
        logger.exception("❌ [SUBSCRIBE] Ошибка создания крипто-инвойса для user=%s tariff=%s", user_id, tariff_id)
        await callback.message.answer("Ошибка создания крипто-инвойса. Попробуйте позже.")
        return

    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=f"💎 Оплатить {usdt_amount} USDT", url=pay_url)],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="subscribe")]
        ]
    )
    await callback.message.answer(
        (
            f"Для оплаты пакета <b>{tariff.name}</b> используйте кнопку ниже.\n"
            f"Начисление: <b>+{tariff.duration_days} tokenX</b>\n"
            f"Сумма: <b>{usdt_amount} USDT</b> (конвертация по актуальному курсу)"
        ),
        parse_mode="HTML",
        reply_markup=markup
    )
    await callback.answer()
