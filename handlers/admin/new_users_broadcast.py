"""Рассылка для пользователей, которые ни разу не платили: общий конструктор."""

from aiogram import Router

from db.base import get_session
from db.users import get_user_ids_never_paid
from utils.broadcast_base import register_broadcast_constructor

router = Router()


async def _audience_never_paid() -> list[int]:
    async with get_session() as session:
        return await get_user_ids_never_paid(session)


register_broadcast_constructor(
    router,
    start_trigger="trial_broadcast_start",
    prefix="trial_broadcast",
    title="🎯 **Конструктор рассылки для неплативших**\n\nНастройте сообщение и отправьте только пользователям, которые ещё ни разу не покупали.",
    send_button_label="🚀 Отправить",
    start_status_text="⏳ Рассылка начинается...",
    summary_title="✅ **Trial-рассылка завершена!**",
    total_label="Всего пользователей (никогда не платили)",
    audience_fetcher=_audience_never_paid,
)
