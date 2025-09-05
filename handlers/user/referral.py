"""
Обработчики реферальной системы пользователя: генерация ссылки, просмотр своих рефералов.
"""
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from db.users import get_ref_link, User
from db.base import get_session
from sqlalchemy import select, func

import config
from utils.keyboards import back_button

router = Router()

REFERRAL_LINK_TEXT = (
    "<b>👥 Пригласи друга и получи бонус!</b>\n\n"
    "Отправь эту ссылку друзьям — за каждого нового пользователя ты получишь <b>{ref_gift} дня</b> подписки!\n\n"
    "🔗 Ваша ссылка:\n{ref_link}\n\n"
    "👤 Приглашено: <b>{count}</b> чел."
)

async def get_referral_text(bot: Bot, user_id: int) -> str:
    """Формирует текст с реферальной ссылкой, количеством рефералов и бонусом."""
    bot_username = (await bot.me()).username
    ref_link = get_ref_link(bot_username, user_id)
    async with get_session() as session:
        result = await session.execute(select(func.count()).select_from(User).where(User.referrer_id == user_id))
        count = result.scalar_one()
    return REFERRAL_LINK_TEXT.format(ref_link=ref_link, count=count, ref_gift=config.REF_GIFT_DAYS)

@router.callback_query(F.data == "invite_friend")
async def invite_friend_callback(callback: CallbackQuery, bot: Bot):
    """Показывает пользователю его реферальную ссылку, количество приглашённых и бонусные дни."""
    text = await get_referral_text(bot, callback.from_user.id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_button("profile"))

@router.message(Command("invite"))
async def invite_friend_command(message: Message, bot: Bot):
    """Обработчик команды /invite."""
    text = await get_referral_text(bot, message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=back_button("profile"))

@router.callback_query(F.data == "my_referrals")
async def my_referrals_callback(callback: CallbackQuery, bot: Bot):
    """Обрабатывает нажатие на кнопку 'Мои рефералы', показывая ту же информацию, что и 'Пригласить друга'."""
    text = await get_referral_text(bot, callback.from_user.id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_button("profile"))

async def get_referral_stats(session, user_id: int):
    """
    Возвращает (count, level, is_vip) для пользователя:
    - count: количество рефералов
    - level: 1 (по умолчанию), 2 (1+), 3 (3+), 4 (10+), 5 (30+)
    - is_vip: True если уровень 3 или выше
    """
    result = await session.execute(
        select(func.count()).select_from(User).where(User.referrer_id == user_id)
    )
    count = result.scalar_one()
    if count >= 30:
        level = 5
    elif count >= 10:
        level = 4
    elif count >= 3:
        level = 3
    elif count >= 1:
        level = 2
    else:
        level = 1
    is_vip = level >= 4
    return count, level, is_vip
