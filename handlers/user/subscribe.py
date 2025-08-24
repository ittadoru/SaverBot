"""Подписка: выбор тарифа и генерация ссылки на оплату."""
import logging
from contextlib import suppress

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError

from db.base import get_session
from db.tariff import get_all_tariffs, get_tariff_by_id
from utils.payment import create_payment


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
            text=f"{t.name} — {t.price} RUB",
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

    try:
        me = await callback.bot.get_me()
        payment_url, payment_id = create_payment(
            user_id=user_id,
            amount=tariff.price,
            description=f"Подписка: {tariff.name}",
            bot_username=me.username or "bot",
            metadata={
                "user_id": str(user_id),
                "tariff_id": str(tariff.id)
            }
        )
        logger.info(
            "💸 [SUBSCRIBE] Создан платёж %s для user=%s tariff=%s price=%s", payment_id, user_id, tariff.id, tariff.price
        )
    except Exception as e:
        logger.exception("❌ [SUBSCRIBE] Ошибка создания платежа для user=%s tariff=%s", user_id, tariff_id)
        await callback.message.answer("Ошибка создания платежа. Попробуйте позже.", show_alert=True)
        return

    markup = InlineKeyboardBuilder()
    markup.button(text="💸 Оплатить", url=payment_url)
    markup.adjust(1)

    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            f"💳 Для оплаты тарифа <b>{tariff.name}</b> нажмите на кнопку оплаты",
            parse_mode=PARSE_MODE,
            reply_markup=markup.as_markup(),
        )
    await callback.answer()
