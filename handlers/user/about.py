
"""Информация о возможностях и бонусах AtariSaver для пользователя."""

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton


router = Router()

@router.callback_query(F.data == "more_info")
async def about_handler(callback: types.CallbackQuery) -> None:
    """
    Отвечает пользователю информацией о функционале бота.
    """
    about_text = (
        "<b>👋 Привет! Я — AtariSaver</b>\n"
        "<i>Твой элитный помощник для скачивания видео и аудио!</i>\n\n"
        "<b>✨ Возможности:</b>\n"
        "<b>•</b> Быстрое скачивание видео и аудио с YouTube, TikTok, Instagram.\n"
        "<b>•</b> Поддержка разных форматов и платформ.\n\n"
        "<b>💎 Преимущества подписки:</b>\n"
        "<b>•</b> Максимальные лимиты на скачивания и размер файлов.\n"
        "<b>•</b> Нет рекламы.\n"
        "<b>•</b> Лучшее качество YouTube.\n"
        "<b>•</b> Оформить подписку: /subscribe или через Профиль.\n\n"
        "<b>🤝 Реферальная программа:</b>\n"
        "<b>•</b> Приглашай друзей и получай бонусы!\n"
        "<b>•</b> Подробнее о реферальных уровнях — по кнопке ниже.\n\n"
        "<b>❓ Вопросы?</b>\n"
        "— Пиши в <b>техподдержку</b> через меню или команду /help."
    )

    await callback.message.edit_text(
        about_text, reply_markup=get_about_keyboard(), parse_mode="HTML"
    )
    await callback.answer()


def get_about_keyboard():
    """Клавиатура: Подробнее о рефералах + Назад в профиль."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="start")
    )
    return builder.as_markup()