"""Рекламная рассылка: подключение общего конструктора (аудитория без активной подписки)."""

from aiogram import Router

from db.base import get_session
from db.users import get_user_ids_without_subscription
from utils.broadcast_base import register_broadcast_constructor

router = Router()


async def _audience_without_subscription() -> list[int]:
    async with get_session() as session:
        return await get_user_ids_without_subscription(session)


register_broadcast_constructor(
    router,
    start_trigger="ad_broadcast_start",
    prefix="ad_broadcast",
    title="📢 **Конструктор рекламной рассылки**\n\nИспользуйте кнопки ниже для настройки, предпросмотра и отправки.",
    send_button_label="🚀 Отправить",
    start_status_text="⏳ Рассылка начинается... Вы получите отчет по завершении.",
    summary_title="✅ **Рекламная рассылка завершена!**",
    total_label="Всего пользователей для рассылки",
    audience_fetcher=_audience_without_subscription,
)
