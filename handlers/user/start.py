
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

# --- вспомогатели для работы с контекстом (Message или CallbackQuery) ---
def _is_callback(ctx) -> bool:
    return isinstance(ctx, types.CallbackQuery)

def _get_message(ctx) -> types.Message:
    return ctx.message if _is_callback(ctx) else ctx

async def send_or_edit(
    ctx,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
    edit_if_callback: bool = True,
):
    """
    Если ctx — CallbackQuery и edit_if_callback=True -> пытаемся редактировать callback.message
    Иначе — отправляем новое сообщение через message.answer()
    """
    msg = _get_message(ctx)
    if _is_callback(ctx) and edit_if_callback:
        try:
            # пробуем редактировать существующее сообщение
            await msg.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            # если редактирование не удалось (например, MessageNotModified, или устарело) —
            # fallback: отправим новое сообщение
            await msg.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await msg.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


# --- функции из предыдущего рефакторинга, адаптированные для ctx ---
def parse_ref_args(ctx, user_id: int):
    message = _get_message(ctx)
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


async def register_user(session, ctx, referrer_id: int | None):
    message = _get_message(ctx)
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


async def process_referral_bonus(session, ctx, user_id: int, referrer_id: int):
    message = _get_message(ctx)
    try:
        # уведомляем нового
        await message.answer("Ты получил бонус за реферала! (3 дня подписки)")
        await add_subscriber_with_duration(session, user_id, REF_GIFT_DAYS)

        # уведомляем реферера и начисляем
        await message.bot.send_message(referrer_id, "Ты получил бонус за реферала! (3 дня подписки)")
        await add_subscriber_with_duration(session, referrer_id, REF_GIFT_DAYS)
        logger.info(f"🎁 [START] Начислен бонус (+3 дня) подписки рефереру {referrer_id} за нового пользователя {user_id}")

        ref_count, level, _ = await get_referral_stats(session, referrer_id)

        # уровни
        if ref_count == 30:
            await add_subscriber_with_duration(session, referrer_id, SUBSCRIPTION_LIFETIME_DAYS)
            try:
                await message.bot.send_message(referrer_id, "🎉 Поздравляем! Вы достигли 5 уровня (30 рефералов) и получили бессрочную подписку!")
            except Exception:
                pass
            logger.info(f"🏆 [REFERAL] Реферер {referrer_id} получил бессрочную подписку за 5 уровень ({ref_count} рефералов)")
        elif ref_count == 10:
            try:
                await message.bot.send_message(referrer_id, "🎉 Поздравляем! Вы достигли 4 уровня (10 рефералов) и получили VIP-статус!")
            except Exception:
                pass
            logger.info(f"⭐️ [REFERAL] Реферер {referrer_id} стал VIP за 4 уровень ({ref_count} рефералов)")
        elif ref_count == 3:
            try:
                await message.bot.send_message(referrer_id, "🎉 Поздравляем! Вы достигли 3 уровня (3 реферала) и улучшили лимиты!")
            except Exception:
                pass
            logger.info(f"🥉 [REFERAL] Реферер {referrer_id} получил бонус за 3 уровень ({ref_count} рефералов)")
        elif ref_count == 1:
            try:
                await message.bot.send_message(referrer_id, "🎉 Поздравляем! Вы достигли 2 уровня (1 реферал) и улучшили лимиты!")
            except Exception:
                pass
            logger.info(f"🥈 [REFERAL] Реферер {referrer_id} получил бонус за 2 уровень ({ref_count} рефералов)")

    except Exception as e:
        logger.error(f"❌ [START] Ошибка при начислении бонуса рефереру {referrer_id}: {e}")


async def send_welcome_message(ctx, promo_code: str | None):
    # промо — обычно хотим отправить отдельным сообщением, поэтому edit_if_callback=False
    if promo_code:
        promo_text = (
            f"Подарок новому пользователю, промокод на {PROMO_DURATION_DAYS} дней подписки:\n"
            f"<pre>{promo_code}</pre>\nАктивируй его через меню профиля.\n\n"
        )
        await send_or_edit(ctx, promo_text, parse_mode="HTML", edit_if_callback=False)


async def notify_support_group(bot, user_id: int, username_raw: str, referrer_id: int | None):
    try:
        await bot.send_message(
            SUPPORT_GROUP_ID,
            text=f"👤 Новый пользователь\n\nID: {user_id}\nИмя: {username_raw}\nРеферал: {referrer_id}",
            message_thread_id=NEW_USER_TOPIC_ID,
        )
    except Exception:
        logger.exception("Не удалось отправить уведомление в поддержку")


async def show_main_menu(ctx):
    message = _get_message(ctx)
    await send_or_edit(
        ctx,
        MAIN_MENU_TEXT.format(username=message.from_user.username),
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML",
        edit_if_callback=True,  # при callback'е — редактировать текущее сообщение
    )


# ================== единый flow для /start и callback_data="start" ==================
@router.message(Command("start"))
async def cmd_start_message(message: types.Message):
    # вызываем единый flow; для обычной команды редактируем не будем
    await start_flow(message)


@router.callback_query(F.data == "start")
async def cmd_start_callback(callback: CallbackQuery):
    # вызываем единый flow; для callback'а будем редактировать сообщение
    await start_flow(callback)
    # обязательно answer() чтобы убрать "крутилку" в клиенте
    try:
        await callback.answer()
    except Exception:
        pass


async def start_flow(ctx):
    """
    ctx: types.Message | types.CallbackQuery
    общая логика регистрации / начислений / показа меню
    """
    message = _get_message(ctx)
    user_id = message.from_user.id
    username_raw = message.from_user.username or message.from_user.full_name

    # парсим реферала из того сообщения, откуда пришёл запрос
    referrer_id = parse_ref_args(ctx, user_id)

    bot_user = await message.bot.get_me()
    if user_id == bot_user.id:
        return

    async with get_session() as session:
        is_new, promo_code = await register_user(session, ctx, referrer_id)

        if is_new and referrer_id:
            await process_referral_bonus(session, ctx, user_id, referrer_id)

        if is_new:
            await send_welcome_message(ctx, promo_code)
            await notify_support_group(message.bot, user_id, username_raw, referrer_id)

    await show_main_menu(ctx)
