"""
Обработчики реферальной системы пользователя: генерация ссылки, просмотр своих рефералов.
"""

from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold
from db.users import get_ref_link, User
from db.base import get_session
from sqlalchemy import select, func


router = Router()

@router.callback_query(lambda c: c.data == "invite_friend")
async def invite_friend(callback: CallbackQuery):
    """Отправляет пользователю его персональную реферальную ссылку."""
    bot_username = (await callback.bot.me()).username
    user_id = callback.from_user.id
    ref_link = get_ref_link(bot_username, user_id)
    text = (
        "👥 <b>Пригласи друга и получи бонус!</b>\n\n"
        "Отправь эту ссылку друзьям — за каждого нового пользователя ты получишь приятный бонус!\n\n"
        f"{ref_link}"
    )
    await callback.message.answer(text, parse_mode="HTML")

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
    - level: 0 (нет), 1 (1-2), 2 (3-9), 3 (10-29), 4 (30+)
    - is_vip: True если уровень 3 или выше
    """
    result = await session.execute(
        select(func.count()).select_from(User).where(User.referrer_id == user_id)
    )
    count = result.scalar_one()
    if count >= 30:
        level = 4
    elif count >= 10:
        level = 3
    elif count >= 3:
        level = 2
    elif count >= 1:
        level = 1
    else:
        level = 0
    is_vip = level >= 3
    return count, level, is_vip