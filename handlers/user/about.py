
"""Информация о возможностях и бонусах SaverBot для пользователя."""

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton


router = Router()

@router.callback_query(F.data == "more_info")
async def about_handler(callback: types.CallbackQuery) -> None:
    """
    Отвечает пользователю информацией о функционале бота.
    """
    about_text = (
        "<b>👋 Привет! Я — SaverBot!</b>\n\n"
        "Я помогаю скачивать видео с YouTube, TikTok и Instagram прямо в Telegram.\n\n"
        "<b>Возможности:</b>\n"
        "• Быстрое скачивание видео и аудио с популярных платформ.\n"
        "• Удобные ссылки и файлы без лишних действий.\n"
        "• Поддержка разных форматов и платформ.\n\n"
        "<b>Преимущества подписки:</b>\n"
        "• Максимальные лимиты на скачивания и размер файлов.\n"
        "• Нет рекламы.\n"
        "• Лучшее качество YouTube.\n"
        "• Оформить подписку можно через команду /subscribe или в разделе Профиль.\n\n"
        "<b>Реферальная программа:</b>\n"
        "• Приглашай друзей и получай бонусы!\n"
        "• Подробнее о реферальных уровнях — по кнопке ниже.\n\n"
        "<b>Где смотреть прогресс?</b>\n"
        "— В разделе <b>Профиль</b> ты найдёшь всю статистику, бонусы и управление подпиской.\n\n"
        "<b>Вопросы?</b>\n"
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
        InlineKeyboardButton(text="ℹ️ О реферальной программе", callback_data="referral_info")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")
    )
    return builder.as_markup()