from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from payment import create_payment
from utils.redis import get_all_tariffs, get_tariff_by_id


router = Router()

@router.message(Command("subscribe"))
async def subscribe_handler(message: types.Message):
    text = (
        "<b>💎 Преимущества подписки:</b>\n"
        "• Качество видео с YouTube до 720p (выбор разрешения)\n"
        "• Возможность скачать аудио из видео на Youtube\n"
        "• Без ограничений на скачивания\n"
        "• Более быстрые загрузки\n"
        "• Долгое хранение файлов на сервере (1 час)\n"
        "• Приоритетная поддержка\n\n"
        "Выберите вариант подписки:"
    )

    
    tariffs = await get_all_tariffs()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{tariff.name} — {tariff.price} RUB",
            callback_data=f"buy_tariff:{tariff.id}"
        )] for tariff in tariffs
    ])

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")



@router.callback_query(lambda c: c.data and c.data.startswith("buy_tariff:"))
async def payment_callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    try:
        tariff_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    # Получаем тариф из Redis
    tariff = await get_tariff_by_id(tariff_id)
    if not tariff:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    # Создаём платёж
    payment_url, payment_id = create_payment(
        user_id=user_id,
        amount=tariff.price,
        description=f"Подписка: {tariff.name}",
        bot_username="savetokgrambot",
        metadata={
            "user_id": str(user_id),
            "tariff_id": str(tariff.id)
        }
    )

    await callback.message.edit_text(
        f"💳 Для оплаты тарифа <b>{tariff.name}</b> перейдите по ссылке:\n\n{payment_url}",
        parse_mode="HTML"
    )
    await callback.answer()



@router.callback_query(lambda c: c.data == "back_to_subscribe")
async def back_to_subscribe_handler(callback: types.CallbackQuery):
    # Отправляем заново выбор подписки
    text = (
        "<b>💎 Преимущества подписки:</b>\n"
        "• Качество видео с YouTube до 720p (выбор разрешения)\n"
        "• Возможность скачать аудио из видео на Youtube\n"
        "• Без ограничений на скачивания\n"
        "• Более быстрые загрузки\n"
        "• Долгое хранение файлов на сервере (1 час)\n"
        "• Приоритетная поддержка\n\n"
        "Выберите вариант подписки:"
    )
    tariffs = await get_all_tariffs()
    # Создаём список кнопок
    buttons = [
        [InlineKeyboardButton(text=f"{tariff.name} – {tariff.price} RUB", callback_data=f"buy_tariff:{tariff.id}")]
        for tariff in tariffs
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")])

    # Создаём клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
