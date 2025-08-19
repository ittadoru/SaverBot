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
        InlineKeyboardButton(text="📊 Мои рефералы", callback_data="my_referrals")
    )
    builder.row(InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="more_info"))
    return builder.as_markup()

MAIN_MENU_TEXT = (
    "👋 <b>Привет, {username}!</b>\n\n"
    "SaverBot — твой помощник для скачивания видео и управления подпиской.\n\n"
    "<b>Возможности:</b>\n"
    "• Скачивай видео с YouTube, TikTok, Instagram\n"
    "• Следи за лимитами и историей скачиваний\n"
    "• Получай бонусы и расширяй возможности через рефералов и промокоды\n"
    "• Оформи подписку для расширенного функционала\n"
    "• Всегда доступна поддержка и подробная статистика\n\n"
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
