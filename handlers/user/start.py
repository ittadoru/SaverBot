"""Start flow: registration, referral rewards and profile summary in start menu."""

import logging
from typing import Optional, Union

from aiogram import F, Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery

from db.base import get_session
from db.users import add_or_update_user, is_user_exists, log_user_activity
from db.tokens import add_bonus_tokens, add_token_x, grant_welcome_token_x
from config import (
    SUPPORT_GROUP_ID,
    NEW_USER_TOPIC_ID,
    WELCOME_BONUS_TOKEN_X,
    REFERRAL_BONUS_TOKENS,
    REFERRAL_BONUS_TOKEN_X,
)
from handlers.user.menu import MAIN_MENU_TEXT, get_main_menu_keyboard
from handlers.user.tokens import build_profile_block

logger = logging.getLogger(__name__)

router = Router()


def parse_ref_args(message: types.Message, user_id: int) -> Optional[int]:
    args = message.get_args() if hasattr(message, "get_args") else ""
    if not args and message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2:
            args = parts[1]

    if args.startswith("ref_"):
        try:
            ref_id = int(args[4:])
            if ref_id != user_id:
                return ref_id
        except Exception:
            pass
    return None


async def register_user(session, user_id: int, first_name: str, username: str, referrer_id: Optional[int]):
    is_new = not await is_user_exists(session, user_id)
    valid_referrer_id: Optional[int] = None
    if is_new and referrer_id and await is_user_exists(session, referrer_id):
        valid_referrer_id = referrer_id

    await add_or_update_user(
        session,
        user_id,
        first_name=first_name,
        username=username,
        referrer_id=valid_referrer_id if is_new else None,
    )
    await log_user_activity(session, user_id)
    if is_new:
        await grant_welcome_token_x(session, user_id, WELCOME_BONUS_TOKEN_X)
    return is_new, valid_referrer_id


async def process_referral_bonus(session, referrer_id: int, bot: Bot):
    try:
        await add_bonus_tokens(session, referrer_id, REFERRAL_BONUS_TOKENS)
        await add_token_x(session, referrer_id, REFERRAL_BONUS_TOKEN_X)
        await bot.send_message(
            referrer_id,
            (
                "🎁 По твоей ссылке зарегистрировался новый пользователь!\n"
                f"Начислено: +{REFERRAL_BONUS_TOKENS} токенов и +{REFERRAL_BONUS_TOKEN_X} tokenX."
            ),
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при бонусе рефереру {referrer_id}: {e}")


async def send_welcome_message(user_id: int, bot: Bot):
    await bot.send_message(
        user_id,
        (
            "🎉 Добро пожаловать!\n"
            f"Стартовый бонус: +{WELCOME_BONUS_TOKEN_X} tokenX.\n"
            "Обычные токены обновляются каждый день автоматически."
        ),
    )


async def notify_support_group(bot: Bot, user_id: int, username_raw: str, referrer_id: Optional[int]):
    await bot.send_message(
        SUPPORT_GROUP_ID,
        text=f"👤 Новый пользователь\n\nID: <code>{user_id}</code>\nИмя: {username_raw}\nРеферал: <code>{referrer_id}</code>",
        message_thread_id=NEW_USER_TOPIC_ID,
        parse_mode="HTML"
    )


# ----------------- единый flow для Message | CallbackQuery -----------------

async def start_flow(event: Union[Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        msg = event.message
        user = event.from_user
    else:
        msg = event
        user = event.from_user

    user_id = user.id
    username_raw = user.username or user.full_name

    # referrer
    referrer_id = parse_ref_args(msg, user_id)

    bot_user = await msg.bot.get_me()
    if user_id == bot_user.id:
        return

    async with get_session() as session:
        is_new, valid_referrer_id = await register_user(
            session,
            user_id,
            user.first_name,
            user.username,
            referrer_id,
        )

        if is_new and valid_referrer_id:
            await process_referral_bonus(session, valid_referrer_id, msg.bot)
        await session.commit()

        if is_new:
            await send_welcome_message(user_id, msg.bot)
            await notify_support_group(msg.bot, user_id, username_raw, valid_referrer_id)

    # показать главное меню
    profile_block = await build_profile_block(user_id)
    text = MAIN_MENU_TEXT.format(username=user.username or "", profile_block=profile_block)
    kb = get_main_menu_keyboard()
    try:
        if isinstance(event, CallbackQuery):
            await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await msg.answer(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            if isinstance(event, CallbackQuery):
                await event.answer("Ты уже здесь 👌", show_alert=False)
        else:
            # fallback на новое сообщение
            await msg.answer(text, reply_markup=kb, parse_mode="HTML")

    if isinstance(event, CallbackQuery):
        await event.answer()


# ----------------- хендлеры -----------------

@router.message(Command("start"))
async def cmd_start(message: Message):
    await start_flow(message)


@router.callback_query(F.data == "start")
async def callback_start(callback: CallbackQuery):
    await start_flow(callback)
