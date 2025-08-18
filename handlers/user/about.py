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
        "Здесь ты можешь скачивать видео с YouTube, TikTok и Instagram, а также получать бонусы и расширять свои возможности с помощью реферальной программы!\n\n"
        "<b>Реферальная программа:</b>\n"
        "• Приглашай друзей по своей персональной ссылке — за каждого нового пользователя ты получаешь +1 к счётчику рефералов.\n"
        "• Чем больше рефералов, тем выше твой <b>уровень</b> и больше привилегий!\n\n"
        "<b>Уровни и бонусы:</b>\n"
        "1 уровень — 1–2 реферала: стандартные лимиты.\n"
        "2 уровень — 3–9 рефералов: увеличенный лимит скачиваний.\n"
        "3 уровень — 10–29 рефералов: <b>VIP-статус</b> (максимальные лимиты).\n"
        "4 уровень — 30+ рефералов: <b>бессрочная подписка</b> (все возможности навсегда).\n\n"
        "<b>Как повысить уровень?</b>\n"
        "— Просто приглашай друзей! Прогресс и текущий уровень всегда видны в твоём профиле.\n\n"
        "<b>Бонусы за рефералов:</b>\n"
        "• За каждого приглашённого — +1 день подписки.\n"
        "• Достигая новых уровней, ты получаешь VIP-статус или бессрочную подписку автоматически.\n\n"
        "<b>Важно:</b> Все подробности и твой прогресс смотри в разделе <b>Профиль</b>. Если возникнут вопросы — обратись в <b>техподдержку</b>!"
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