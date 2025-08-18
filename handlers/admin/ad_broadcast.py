"""
Рекламная рассылка: подключение конструктора для пользователей без подписки.
"""

from aiogram import Router

from db.base import get_session
from db.users import get_user_ids_without_subscription
from utils.broadcast_base import register_broadcast_constructor

router = Router()


async def _audience_without_subscription() -> list[int]:
    """
    Возвращает user_id пользователей без активной подписки.
    """
    async with get_session() as session:
        return await get_user_ids_without_subscription(session)


register_broadcast_constructor(
    router,
    start_trigger="ad_broadcast_start",
    prefix="ad_broadcast",
    title="💸 Рекламная рассылка\n\nРасскажите о новых возможностях или скидках тем, у кого нет подписки.",
    send_button_label="Отправить",
    start_status_text="⏳ Рассылка началась! По завершении придёт отчёт.",
    summary_title="🎉 Рекламная рассылка завершена!",
    total_label="Пользователей для рассылки",
    audience_fetcher=_audience_without_subscription,
)
