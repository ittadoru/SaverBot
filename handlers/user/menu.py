"""
Главное меню пользователя с основными разделами бота (без обработчиков рефералов).
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
    builder.row(
        InlineKeyboardButton(text="👥 Пригласить друга", callback_data="invite_friend"),
        InlineKeyboardButton(text="🤝 Об уровнях", callback_data="referral_info")
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="more_info"),
    )
    return builder.as_markup()

MAIN_MENU_TEXT = (
    "<b>👋 Привет, {username}!</b>\n"
    "<i>AtariSaver — твой помощник для скачивания видео.</i>\n\n"
    "<b>✨ Возможности:</b>\n"
    "<b>•</b> Скачивай видео и аудио с YouTube, TikTok, Instagram\n"
    "<b>•</b> Следи за лимитами и историей\n"
    "<b>•</b> Получай бонусы за рефералов и промокоды\n"
    "<b>•</b> Оформи подписку — получи максимум\n"
    "<b>•</b> Поддержка и статистика всегда под рукой\n\n"
    "Выбери нужный раздел ниже!"
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
    """Обработчик для кнопки 'Мой профиль'."""
    await callback.message.edit_text(
        MAIN_MENU_TEXT.format(username=callback.from_user.username),
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
