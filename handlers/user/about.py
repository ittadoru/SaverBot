
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
        "<i>Я помощник для скачивания контента по токенам.</i>\n\n"
        "<b>✨ Что умею:</b>\n"
        "<b>•</b> TikTok и Instagram — всегда максимальное качество.\n"
        "<b>•</b> YouTube — выбор 480p / 720p / 1080p / 1440p / 4k и аудио.\n"
        "<b>•</b> Видео длиннее 3 часов не поддерживаются.\n\n"
        "<b>💱 Токены:</b>\n"
        "<b>•</b> Ежедневно даю 100 обычных токенов.\n"
        "<b>•</b> tokenX — отдельная платная валюта для 1440p/4k.\n"
        "<b>•</b> Обмен: 1 tokenX = 15 токенов.\n\n"
        "<b>🤝 Приглашения:</b>\n"
        "<b>•</b> За каждого приглашенного друга: +50 токенов и +1 tokenX.\n\n"
        "<b>❓ Вопросы?</b>\n"
        "Пиши в поддержку через меню или команду /help."
    )

    await callback.message.edit_text(
        about_text, reply_markup=get_about_keyboard(), parse_mode="HTML"
    )
    await callback.answer()


def get_about_keyboard():
    """Клавиатура с возвратом в стартовое меню."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="start")
    )
    return builder.as_markup()
