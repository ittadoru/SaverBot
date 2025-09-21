
"""Старт: регистрация/обновление пользователя и выдача приветственного промокода новым."""

import logging

import random
from typing import Optional

from aiogram import F, Router, types
from aiogram.filters import Command

from db.base import get_session
from db.promocodes import add_promocode, get_promocode
from db.users import add_or_update_user, is_user_exists, log_user_activity
from db.subscribers import add_subscriber_with_duration
from handlers.user.referral import get_referral_stats
from config import SUBSCRIPTION_LIFETIME_DAYS, SUPPORT_GROUP_ID, NEW_USER_TOPIC_ID
from handlers.user.menu import MAIN_MENU_TEXT, get_main_menu_keyboard

logger = logging.getLogger(__name__)

PROMO_DURATION_DAYS = 7
PROMO_PREFIX = "WELCOME"
PROMO_RANDOM_MIN = 100_000
PROMO_RANDOM_MAX = 999_999
PROMO_MAX_TRIES = 5
REF_GIFT_DAYS = 10

router = Router()

async def _generate_unique_promocode(session, tries: int = PROMO_MAX_TRIES) -> str | None:
    """
    Пытается создать и сохранить уникальный промокод, возвращает код или None.
    Проверяем коллизии через запрос существующего кода (быстро и просто).
    """
    for attempt in range(1, tries + 1):
        code = f"{PROMO_PREFIX}-{random.randint(PROMO_RANDOM_MIN, PROMO_RANDOM_MAX)}"
        exists = await get_promocode(session, code)
        if exists:
            continue
        await add_promocode(session, code, duration_days=PROMO_DURATION_DAYS)
        return code
    logger.warning(
        "⚠️ [START] Не удалось сгенерировать уникальный промокод после %d попыток", tries
    )
    return None

def parse_ref_args(message: types.Message, user_id: int) -> Optional[int]:
    args = message.get_args() if hasattr(message, "get_args") else ""
    if not args and message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2:
            args = parts[1]

    if args and args.startswith("ref_"):
        try:
            ref_id = int(args[4:])
            if ref_id != user_id:
                return ref_id
        except Exception:
            pass
    return None


async def register_user(session, message: types.Message, referrer_id: Optional[int]):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username

    is_new = not await is_user_exists(session, user_id)
    user = await add_or_update_user(
        session,
        user_id,
        first_name=first_name,
        username=username,
        referrer_id=referrer_id if is_new else None,
    )
    await log_user_activity(session, user_id)

    promo_code = None
    if is_new:
        promo_code = await _generate_unique_promocode(session)

    return is_new, promo_code


async def process_referral_bonus(session, message: types.Message, user_id: int, referrer_id: int):
    try:
        await message.answer("Ты получил бонус за реферала! (3 дня подписки)")
        await add_subscriber_with_duration(session, user_id, REF_GIFT_DAYS)

        await message.bot.send_message(referrer_id, "Ты получил бонус за реферала! (3 дня подписки)")
        await add_subscriber_with_duration(session, referrer_id, REF_GIFT_DAYS)
        logger.info(f"🎁 [START] Начислен бонус рефереру {referrer_id} за нового пользователя {user_id}")

        ref_count, level, _ = await get_referral_stats(session, referrer_id)

        if ref_count == 30:
            await add_subscriber_with_duration(session, referrer_id, SUBSCRIPTION_LIFETIME_DAYS)
            await message.bot.send_message(referrer_id, "🎉 Поздравляем! Бессрочная подписка!")
        elif ref_count == 10:
            await message.bot.send_message(referrer_id, "🎉 Поздравляем! Вы стали VIP!")
        elif ref_count == 3:
            await message.bot.send_message(referrer_id, "🎉 3 уровень! Лимиты увеличены!")
        elif ref_count == 1:
            await message.bot.send_message(referrer_id, "🎉 2 уровень! Лимиты улучшены!")

    except Exception as e:
        logger.error(f"❌ Ошибка при бонусе рефереру {referrer_id}: {e}")


async def send_welcome_message(message: types.Message, promo_code: Optional[str]):
    if promo_code:
        promo_text = (
            f"Подарок новому пользователю: промокод на {PROMO_DURATION_DAYS} дней подписки:\n"
            f"<pre>{promo_code}</pre>\nАктивируй его через меню профиля.\n\n"
        )
        await message.answer(promo_text, parse_mode="HTML")


async def notify_support_group(bot, user_id: int, username_raw: str, referrer_id: Optional[int]):
    await bot.send_message(
        SUPPORT_GROUP_ID,
        text=f"👤 Новый пользователь\n\nID: {user_id}\nИмя: {username_raw}\nРеферал: {referrer_id}",
        message_thread_id=NEW_USER_TOPIC_ID,
    )


async def show_main_menu(message: types.Message):
    await message.answer(
        MAIN_MENU_TEXT.format(username=message.from_user.username),
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
    )


# ================== Основные хендлеры ==================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username_raw = message.from_user.username or message.from_user.full_name

    referrer_id = parse_ref_args(message, user_id)

    bot_user = await message.bot.get_me()
    if user_id == bot_user.id:
        return

    async with get_session() as session:
        is_new, promo_code = await register_user(session, message, referrer_id)

        if is_new and referrer_id:
            await process_referral_bonus(session, message, user_id, referrer_id)

        if is_new:
            await send_welcome_message(message, promo_code)
            await notify_support_group(message.bot, user_id, username_raw, referrer_id)

    await show_main_menu(message)


@router.callback_query(F.data == "start")
async def callback_start(callback: types.CallbackQuery):
    await cmd_start(callback.message)
    await callback.answer()