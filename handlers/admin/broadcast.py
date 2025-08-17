"""Общая рассылка: подключение общего конструктора."""

from aiogram import Router

from db.base import get_session
from db.users import get_all_user_ids
from utils.broadcast_base import register_broadcast_constructor

router = Router()


async def _audience_all() -> list[int]:
    async with get_session() as session:
        return await get_all_user_ids(session)


register_broadcast_constructor(
    router,
    start_trigger="broadcast_start",
    prefix="broadcast",
    title="📢 **Конструктор общей рассылки**\n\nИспользуйте кнопки ниже для настройки, предпросмотра и отправки.",
    send_button_label="🚀 Отправить",
    start_status_text="⏳ Рассылка всем пользователям начинается...",
    summary_title="✅ **Общая рассылка завершена!**",
    total_label="Всего пользователей для рассылки",
    audience_fetcher=_audience_all,
)
