"""
Общая рассылка: подключение конструктора рассылки для всех пользователей.
"""

from aiogram import Router

from db.base import get_session
from db.users import get_all_user_ids
from utils.broadcast_base import register_broadcast_constructor

router = Router()


async def _audience_all() -> list[int]:
    """
    Возвращает список user_id всех пользователей для рассылки.
    """
    async with get_session() as session:
        return await get_all_user_ids(session)


register_broadcast_constructor(
    router,
    start_trigger="broadcast_start",
    prefix="broadcast",
    title="📢 Рассылка для всех\n\nОтправьте важную новость или акцию всем пользователям. Не волнуйтесь — вы получите отчёт!",
    send_button_label="Отправить",
    start_status_text="⏳ Рассылка началась! По завершении придёт отчёт.",
    summary_title="🎉 Рассылка завершена!",
    total_label="Пользователей для рассылки",
    audience_fetcher=_audience_all,
)
