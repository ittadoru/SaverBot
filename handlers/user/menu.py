"""Главное меню пользователя с основными разделами бота."""

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# Роутер для пользовательских команд и меню
router = Router()

# Главное меню пользователя (обычные кнопки)
main_menu = InlineKeyboardMarkup(
    inline_keyboard = [
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="myprofile")],
        [InlineKeyboardButton(text="🆘 Начать чат с поддержкой", callback_data="help")],
        [
            InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="promo"),
            InlineKeyboardButton(text="💳 Подписка", callback_data="subscribe"),
        ],
        [InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="more_info")]
    ],
    resize_keyboard=True
)
keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
        ]
    )


@router.message(F.text == "/profile")
async def show_main_menu(message: Message):
    """
    Показывает главное меню пользователю при /start
    """
    await message.answer(
        f"👋 <b>Здравствуй {message.from_user.username}, твой профиль как всегда прекрасен!</b>\n\n"
        "<b>Что умеет бот:</b>\n"
        "• 👤 <b>Мой профиль</b> — статус подписки, лимиты и твоя статистика.\n"
        "• 🆘 <b>Чат с поддержкой</b> — чат с поддержкой для решения проблемы.\n"
        "• 🎟 <b>Ввести промокод</b> — активируй возможности подписки.\n"
        "• 💳 <b>Подписка</b> — купить/продлить подписку.\n"        
        "• ℹ️ <b>Подробнее</b> — сообщение от разработчика.\n\n"
        "Выбирай нужный раздел ниже и пользуйся ботом с удовольствием!",
        reply_markup=main_menu,
        parse_mode="HTML"
    )

# Добавляйте новые обработчики для других кнопок и логики меню по мере необходимости
@router.callback_query(lambda c: c.data == "profile")
async def show_profile(callback: CallbackQuery):
    """
    Обработчик для кнопки "Мой профиль".
    Здесь можно добавить логику отображения профиля пользователя.
    """
    await callback.message.edit_text(
        f"👋 <b>Здравствуй {callback.from_user.username}, твой профиль как всегда прекрасен!</b>\n\n"
        "<b>Что умеет бот:</b>\n"
        "• 👤 <b>Мой профиль</b> — статус подписки, лимиты и твоя статистика.\n"
        "• 🆘 <b>Чат с поддержкой</b> — чат с поддержкой для решения проблемы.\n"
        "• 🎟 <b>Ввести промокод</b> — активируй возможности подписки.\n"
        "• 💳 <b>Подписка</b> — купить/продлить подписку.\n"        
        "• ℹ️ <b>Подробнее</b> — сообщение от разработчика.\n\n"
        "Выбирай нужный раздел ниже и пользуйся ботом с удовольствием!",
        reply_markup=main_menu,
        parse_mode="HTML"
    )