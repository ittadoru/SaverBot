from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def back_button(callback_data: str = "admin_menu") -> InlineKeyboardMarkup:
    """Клавиатура с одной кнопкой 'Назад'."""
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data=callback_data)
    return kb.as_markup()


def pagination_keyboard(current_page: int, total_pages: int, prefix: str = "page", extra_buttons=None) -> InlineKeyboardMarkup:
    """
    Универсальная клавиатура для пагинации (перелистывания).
    extra_buttons: список (text, callback_data) для добавления в конец.
    """
    kb = InlineKeyboardBuilder()
    if current_page > 1:
        kb.button(text="⬅️", callback_data=f"{prefix}:{current_page-1}")
    kb.button(text=f"{current_page}/{total_pages}", callback_data="noop")
    if current_page < total_pages:
        kb.button(text="➡️", callback_data=f"{prefix}:{current_page+1}")
    if extra_buttons:
        for text, cb in extra_buttons:
            kb.button(text=text, callback_data=cb)
    return kb.as_markup()

def subscribe_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой подписки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="subscribe")]
        ]
    )