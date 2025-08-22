"""Поддержка (админ): ответы в темах и закрытие тикетов."""

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.types import Message

from config import SUPPORT_GROUP_ID
from db.base import get_session
from db.support import SupportTicket, close_ticket, get_open_ticket_by_topic_id


logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.id == SUPPORT_GROUP_ID, F.is_topic_message)
router.callback_query.filter(F.chat.id == SUPPORT_GROUP_ID, F.is_topic_message)

@router.message(F.text.lower().in_(["/stop", "стоп", "закрыть"]))
async def admin_close_ticket_handler(event) -> None:
    """
    Закрывает тикет по команде от администратора.
    Уведомляет пользователя о закрытии диалога.
    """
    if isinstance(event, Message):
        topic_id = event.message_thread_id
        admin_id = event.from_user.id
    else:
        topic_id = event.message.message_thread_id
        admin_id = event.from_user.id

    async with get_session() as session:
        ticket: Optional[SupportTicket] = await get_open_ticket_by_topic_id(
            session, topic_id
        )

        if not ticket:
            if isinstance(event, Message):
                await event.reply("⚠️ Этот тикет уже закрыт.")
            else:
                await event.message.edit_text("⚠️ Этот тикет уже закрыт.")
                await event.answer()
            return

        user_id = ticket.user_id
        await close_ticket(session, user_id)

        await event.bot.send_message(
            user_id, "❌ Администратор завершил диалог. Вы снова можете пользоваться ботом."
        )

        if isinstance(event, Message):
            await event.reply("✅ Диалог с пользователем закрыт.")
        else:
            await event.message.edit_text("✅ Диалог с пользователем закрыт.")
            await event.answer()
        logger.info(
            "✅ [SUPPORT] Администратор %d закрыл тикет для пользователя %d (тема %d)",
            admin_id,
            user_id,
            topic_id,
        )

@router.message()
async def admin_reply_handler(message: Message) -> None:
    """
    Обрабатывает ответы администраторов в темах поддержки.
    Пересылает сообщение пользователя, если тикет открыт.
    """
    if message.from_user.is_bot:
        return

    topic_id = message.message_thread_id
    admin_id = message.from_user.id

    async with get_session() as session:
        ticket: Optional[SupportTicket] = await get_open_ticket_by_topic_id(
            session, topic_id
        )

        if not ticket:
            await message.reply("⚠️ Этот тикет уже закрыт. Сообщение не доставлено.")
            return

        user_id = ticket.user_id
        try:
            await message.copy_to(
                chat_id=user_id, caption=f"💬 Ответ поддержки:\n{message.caption or ''}"
            )
        except Exception as e:
            logger.error(
                "❌ [SUPPORT] Не удалось доставить сообщение от администратора %d пользователю %d: %s",
                admin_id,
                user_id,
                e,
            )
            await message.reply(f"❗️ Не удалось доставить сообщение пользователю. Ошибка: {e}")
