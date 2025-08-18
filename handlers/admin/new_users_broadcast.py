"""
Рассылка для новых пользователей: подключение конструктора для тех, кто ещё не платил.
"""

from aiogram import Router

from db.base import get_session
from db.users import get_user_ids_never_paid
from utils.broadcast_base import register_broadcast_constructor

router = Router()


async def _audience_never_paid() -> list[int]:
    """
    Возвращает user_id пользователей, которые ни разу не платили.
    """
    async with get_session() as session:
        return await get_user_ids_never_paid(session)


register_broadcast_constructor(
    router,
    start_trigger="trial_broadcast_start",
    prefix="trial_broadcast",
    title="🎯 Для новых пользователей\n\nСообщение получат только те, кто ещё не совершал покупок.",
    send_button_label="Отправить",
    start_status_text="⏳ Рассылка началась! По завершении придёт отчёт.",
    summary_title="🎉 Trial-рассылка завершена!",
    total_label="Пользователей (никогда не платили)",
    audience_fetcher=_audience_never_paid,
)
