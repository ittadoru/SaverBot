"""
Обработчики реферальной системы пользователя: генерация ссылки, просмотр своих рефералов.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold
from db.users import get_ref_link, User
from db.base import get_session


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
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.referrer_id == user_id))
        referrals = result.scalars().all()
    if not referrals:
        text = "У тебя пока нет рефералов. Пригласи друзей и получи бонус!"
    else:
        text = f"{hbold('Твои рефералы')}:\n\n"
        for u in referrals:
            uname = f"@{u.username}" if u.username else f"ID {u.id}"
            text += f"• {uname}\n"
        text += f"\nВсего: {len(referrals)} чел."
    await callback.message.answer(text, parse_mode="HTML")
