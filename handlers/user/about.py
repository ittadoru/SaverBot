import logging

from aiogram import F, Router, types

# Предполагается, что в menu.py есть клавиатура для возврата в главное меню
from .menu import keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "more_info")
async def about_handler(callback: types.CallbackQuery) -> None:
    """
    Отвечает пользователю информацией о функционале бота.
    """
    about_text = (
        "<b>👋 Привет! Я — твой помощник.</b>\n\n"
        "Я создан, чтобы помочь тебе управлять подписками и получать эксклюзивный контент.\n\n"
        "<b>Основные функции:</b>\n"
        "⭐️ <b>Подписка:</b> Оформляй подписку для доступа ко всем возможностям.\n"
        "🎁 <b>Промокоды:</b> Активируй промокоды для получения бонусов.\n"
        "👤 <b>Профиль:</b> Проверяй статус своей подписки.\n\n"
        "Если возникнут вопросы, смело обращайся в <b>техподдержку</b>!"
    )

    logger.info("Пользователь %d запросил информацию о боте.", callback.from_user.id)

    await callback.message.edit_text(
        about_text, reply_markup=keyboard, parse_mode="HTML"
    )
    await callback.answer()
