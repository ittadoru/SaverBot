"""Referral handlers: personal invite link and invited friends counter."""

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func

from db.base import get_session
from db.users import User, get_ref_link
from config import REFERRAL_BONUS_TOKENS, REFERRAL_BONUS_TOKEN_X


router = Router()

REFERRAL_LINK_TEXT = (
    "<b>👥 Пригласи друга и получай токены</b>\n\n"
    f"За каждого нового пользователя по твоей ссылке: "
    f"<b>+{REFERRAL_BONUS_TOKENS} токенов</b> и <b>+{REFERRAL_BONUS_TOKEN_X} tokenX</b>.\n\n"
    "Нажми кнопку ниже, чтобы быстро поделиться ссылкой.\n\n"
    "👤 Приглашено: <b>{count}</b> чел."
)


async def get_referrals_count(session, user_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(User.referrer_id == user_id)
    )
    return int(result.scalar_one() or 0)


async def get_referral_text(user_id: int) -> str:
    async with get_session() as session:
        count = await get_referrals_count(session, user_id)
    return REFERRAL_LINK_TEXT.format(count=count)


def referral_keyboard(ref_link: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Поделиться ссылкой", switch_inline_query=ref_link)
    builder.button(text="⬅️ Назад", callback_data="start")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "invite_friend")
async def invite_friend_callback(callback: CallbackQuery, bot: Bot):
    ref_link = get_ref_link((await bot.me()).username, callback.from_user.id)
    text = await get_referral_text(callback.from_user.id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=referral_keyboard(ref_link))
    await callback.answer()


@router.message(Command("invite"))
async def invite_friend_command(message: Message, bot: Bot):
    ref_link = get_ref_link((await bot.me()).username, message.from_user.id)
    text = await get_referral_text(message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=referral_keyboard(ref_link))
