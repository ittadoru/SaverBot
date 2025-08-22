"""
Обработчики реферальной системы пользователя: генерация ссылки, просмотр своих рефералов.
"""
from aiogram.filters import Command

from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold
from db.users import get_ref_link, User
from db.base import get_session
from sqlalchemy import select, func


router = Router()

async def send_invite_link(user_id: int, bot, message_or_callback):
    """Отправляет пользователю его реферальную ссылку."""
    bot_username = (await bot.me()).username
    ref_link = get_ref_link(bot_username, user_id)
    text = (
        "👥 <b>Пригласи друга и получи бонус!</b>\n\n"
        "Отправь эту ссылку друзьям — за каждого нового пользователя ты получишь приятный бонус!\n\n"
        f"{ref_link}"
    )
    await message_or_callback.answer(text, parse_mode="HTML")

@router.callback_query(lambda c: c.data == "invite_friend")
async def invite_friend_callback(callback: CallbackQuery):
    await send_invite_link(callback.from_user.id, callback.bot, callback.message)

@router.message(Command("invite"))
async def invite_friend_command(message):
    await send_invite_link(message.from_user.id, message.bot, message)

@router.callback_query(lambda c: c.data == "my_referrals")
async def my_referrals(callback: CallbackQuery):
    """Показывает пользователю список или статистику его рефералов."""
    user_id = callback.from_user.id
    async with get_session() as session:
        result = await session.execute(select(User).where(User.referrer_id == user_id))
        referrals = result.scalars().all()

    if not referrals:
        text = "У тебя пока нет рефералов. Пригласи друзей и получи бонус!"
    else:
        ref_list = f"{hbold('Твои рефералы')}:\n\n"
        for u in referrals:
            uname = f"@{u.username}" if u.username else f"ID {u.id}"
            ref_list += f"• {uname}\n"
        ref_list += f"\nВсего: {len(referrals)} чел."
        text = ref_list
    await callback.message.answer(text, parse_mode="HTML")

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