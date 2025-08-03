from aiogram import Router, F, types
from aiogram.types import Message
from utils.redis import r as redis
from config import SUPPORT_GROUP_ID
from utils.support_ticket import get_user_id_by_topic, get_ticket, close_ticket
from utils import logger as log
router = Router()

@router.message(F.chat.id == SUPPORT_GROUP_ID, F.is_topic_message)
async def admin_reply(message: Message):
    topic_id = message.message_thread_id
    user_id = await get_user_id_by_topic(redis, topic_id)
    if not user_id:
        return
    ticket = await get_ticket(redis, user_id)
    if not ticket or ticket["status"] != "open":
        await message.reply("Тикет уже закрыт.")
        return
    # Пересылаем сообщение пользователю
    if message.text:
        await message.bot.send_message(
            user_id,
            f"💬 Ответ поддержки:\n{message.text}"
        )
    if message.photo:
        await message.bot.send_photo(
            user_id,
            message.photo[-1].file_id,
            caption=f"💬 Ответ поддержки:\n{message.caption or ''}"
        )
    log.log_message(f"👨‍💻 Админ ответил пользователю id={user_id} в тикете topic_id={topic_id}: {message.text or '[не текстовое сообщение]'}", emoji="🛠️")

    # Добавьте обработку других типов сообщений по необходимости


@router.message(F.chat.id == SUPPORT_GROUP_ID, F.is_topic_message, F.text == "/stop")
async def admin_close_ticket(message: Message):
    topic_id = message.message_thread_id
    user_id = await get_user_id_by_topic(redis, topic_id)
    if not user_id:
        return
    ticket = await get_ticket(redis, user_id)
    if ticket and ticket["status"] == "open":
        await close_ticket(redis, user_id)
        await message.bot.send_message(
            user_id,
            "❌ Администратор завершил диалог. Бот снова доступен для скачивания видео."
        )
        await message.reply("Диалог с пользователем закрыт.")