"""
Обработчик админ-команды: топ-10 пользователей по количеству рефералов.
Красивое оформление, кнопка "Назад".
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

import logging
from db.base import get_session
from db.users import get_top_referrers


logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "top_referrals")
async def admin_top_referrals(callback: CallbackQuery) -> None:
    """
    Показывает топ-10 пользователей по количеству рефералов с красивым оформлением и кнопкой "Назад".
    """
    admin_id = callback.from_user.id
    try:
        async with get_session() as session:
            top = await get_top_referrers(session, limit=10)
        markup = InlineKeyboardBuilder()
        markup.button(text="⬅️ Назад", callback_data="manage_users")
        markup.adjust(1)

        if not top:
            text = "Нет данных по рефералам."
        else:
            text = "<b>🏆 Топ-10 по рефералам:</b>\n\n"
            medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
            for i, u in enumerate(top, 1):
                medal = medals[i - 1] if i <= len(medals) else "🏅"
                uname = f"<b>@{u.username}</b>" if u.username else f"<code>{u.id}</code>"
                text += (
                    f"{medal} {uname} — <b>{u.ref_count}</b> рефералов | "
                    f"уровень <b>{u.level}</b>\n"
                )

        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=markup.as_markup()
            )
        except Exception as e:
            await callback.answer()
            return

        await callback.answer()
    except Exception as e:
        logger.exception("Ошибка при обработке топа рефералов (user_id=%d): %s", admin_id, e)
        await callback.answer("Произошла ошибка при выводе топа рефералов.", show_alert=True)