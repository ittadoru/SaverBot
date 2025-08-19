"""
Рекламная рассылка: подключение конструктора для пользователей без подписки.
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
    start_trigger="ad_broadcast_start",
    prefix="ad_broadcast",
    title="💸 Рекламная рассылка\n\nРасскажите о новых возможностях или скидках тем, у кого нет подписки.",
    send_button_label="Отправить",
    start_status_text="⏳ Рассылка началась! По завершении придёт отчёт.",
    summary_title="🎉 Рекламная рассылка завершена!",
    total_label="Пользователей для рассылки",
    audience_fetcher=_audience_all,
)
