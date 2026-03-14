"""
Главное меню пользователя с основными разделами бота (без обработчиков рефералов).
"""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard():
    """Возвращает клавиатуру главного меню пользователя."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🕓 История скачиваний", callback_data="download_history"))
    builder.row(InlineKeyboardButton(text="💱 Токены и лимиты", callback_data="tokens_menu"))
    builder.row(InlineKeyboardButton(text="🛒 Купить tokenX", callback_data="subscribe"))
    builder.row(InlineKeyboardButton(text="👥 Пригласить друга", callback_data="invite_friend"))
    builder.row(InlineKeyboardButton(text="🆘 Начать чат с поддержкой", callback_data="help"))
    return builder.as_markup()

MAIN_MENU_TEXT = (
    "<b>👋{username}</b>\n\n"
    "{profile_block}"
)
