from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("subscribe"))
async def subscribe_handler(message: types.Message):
    # Информация о преимуществах подписки и кнопки оплаты
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

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="Оплатить 1 месяц — 49₽",
                url="https://www.youtube.com/watch?v=RlQn_ZWuNa0"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="Оплатить 1 год — 490₽",
                url="https://www.youtube.com/watch?v=RlQn_ZWuNa0"
            ),
        ]
    ])

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
