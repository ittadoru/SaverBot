import logging

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton


logger = logging.getLogger(__name__)

router = Router()

@router.callback_query(F.data == "more_info")
async def about_handler(callback: types.CallbackQuery) -> None:
    """
    Отвечает пользователю информацией о функционале бота.
    """
    about_text = (
        "<b>👋 Привет! Я — твой помощник SaverBot.</b>\n\n"
        "Я создан, чтобы помогать тебе скачивать видео с YouTube, TikTok, Instagram, "
        "управлять подпиской, получать бонусы и поддержку.\n\n"
        "<b>Что я умею:</b>\n"
        "• ⬇️ <b>Скачивание видео</b> — YouTube, TikTok, Instagram (с выбором качества и аудио).\n"
        "• 👤 <b>Профиль</b> — статус подписки, лимиты, твоя статистика.\n"
        "• 🕓 <b>История скачиваний</b> — последние 10 ссылок.\n"
        "• 🎟 <b>Промокоды</b> — активация бонусов.\n"
        "• 💳 <b>Подписка</b> — купить/продлить, снять лимиты.\n"
        "• 🆘 <b>Чат с поддержкой</b> — помощь по любым вопросам.\n"
        "• 📊 <b>Статистика</b> — топ скачиваний по платформам.\n"
        "• ℹ️ <b>Подробнее</b> — узнать о возможностях бота.\n\n"
        "Если возникнут вопросы — смело обращайся в <b>техподдержку</b>!"
    )

    logger.info("Пользователь %d запросил информацию о боте.", callback.from_user.id)

    await callback.message.edit_text(
        about_text, reply_markup=get_back_keyboard(), parse_mode="HTML"
    )
    await callback.answer()

def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="profile"))
    return builder.as_markup()