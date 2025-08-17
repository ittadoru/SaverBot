
"""
Главное меню пользователя с основными разделами бота.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

def get_main_menu_keyboard():
    """Возвращает клавиатуру главного меню пользователя."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👤 Мой профиль", callback_data="myprofile"))
    builder.row(InlineKeyboardButton(text="🕓 История скачиваний", callback_data="download_history"))
    builder.row(InlineKeyboardButton(text="🆘 Начать чат с поддержкой", callback_data="help"))
    builder.row(
        InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="promo"),
        InlineKeyboardButton(text="💳 Подписка", callback_data="subscribe")
    )
    builder.row(InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="more_info"))
    return builder.as_markup()

MAIN_MENU_TEXT = (
    "👋 <b>Здравствуй {username}, твой профиль как всегда прекрасен!</b>\n\n"
    "<b>Что умеет бот:</b>\n"
    "• 👤 <b>Мой профиль</b> — статус подписки, лимиты и твоя статистика.\n"
    "• 🆘 <b>Чат с поддержкой</b> — чат с поддержкой для решения проблемы.\n"
    "• 🕓 <b>История скачиваний</b> — посмотри, что ты уже скачал.\n"
    "• 🎟 <b>Ввести промокод</b> — активируй возможности подписки.\n"
    "• 💳 <b>Подписка</b> — купить/продлить подписку.\n"
    "• ℹ️ <b>Подробнее</b> — сообщение от разработчика.\n\n"
    "Выбирай нужный раздел ниже и пользуйся ботом с удовольствием!"
)

@router.message(F.text == "/profile")
async def show_main_menu(message: Message):
    """Показывает главное меню пользователю по команде /profile."""
    await message.answer(
        MAIN_MENU_TEXT.format(username=message.from_user.username),
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "profile")
async def show_profile(callback: CallbackQuery):
    """Обработчик для кнопки "Мой профиль"."""
    await callback.message.edit_text(
        MAIN_MENU_TEXT.format(username=callback.from_user.username),
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )