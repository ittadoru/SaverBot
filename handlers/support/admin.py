from aiogram import Router, F, types
from aiogram.types import Message
from utils.redis import r as redis
from config import SUPPORT_GROUP_ID
from utils.support_ticket import get_user_id_by_topic, get_ticket, close_ticket
from utils import logger as log

router = Router()


@router.message(F.chat.id == SUPPORT_GROUP_ID, F.is_topic_message)
async def admin_reply(message: Message):
    """
    Обрабатывает ответы админов в теме поддержки.
    Пересылает текстовые и фото сообщения пользователю, если тикет открыт.
    """
    topic_id = message.message_thread_id
    user_id = await get_user_id_by_topic(redis, topic_id)
    if not user_id:
        return

    ticket = await get_ticket(redis, user_id)
    if not ticket or ticket["status"] != "open":
        await message.reply("Тикет уже закрыт.")
        return

    # Пересылаем текстовое сообщение пользователю
    if message.text:
        await message.bot.send_message(
            user_id,
            f"💬 Ответ поддержки:\n{message.text}"
        )

    # Пересылаем фото, если есть
    if message.photo:
        await message.bot.send_photo(
            user_id,
            message.photo[-1].file_id,
            caption=f"💬 Ответ поддержки:\n{message.caption or ''}"
        )

    log.log_message(
        f"👨‍💻 Админ ответил пользователю id={user_id} в тикете topic_id={topic_id}: "
        f"{message.text or '[не текстовое сообщение]'}",
        emoji="🛠️"
    )

    # TODO: Добавить обработку других типов сообщений (документы, аудио и т.п.) по необходимости


@router.message(F.chat.id == SUPPORT_GROUP_ID, F.is_topic_message, F.text == "/stop")
async def admin_close_ticket(message: Message):
    """
    Закрывает тикет по команде /stop от админа.
    Отправляет пользователю уведомление о закрытии диалога.
    """
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
