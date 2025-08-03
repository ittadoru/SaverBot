from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.filters import Command
from utils.redis import r as redis
from config import SUPPORT_GROUP_ID
from states.support import Support
from utils.support_ticket import create_ticket, get_ticket, close_ticket, is_ticket_open
from utils import logger as log
router = Router()

@router.message(Command("help"))
async def start_support(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    ticket = await get_ticket(redis, user_id)
    if ticket and ticket["status"] == "open":
        await message.answer("У вас уже открыт чат с поддержкой. Напишите сообщение.")
    else:
        topic_id = await create_ticket(redis, message.bot, user_id, username, SUPPORT_GROUP_ID)
        log.log_message(f"🆕 Открыт чат поддержки для @{username or 'Без username'} | id={user_id}", emoji="💬")

        await message.answer(
            "🆘 Чат с поддержкой открыт!\n"
            "Чтобы завершить диалог, нажмите на /stop.\n"
            "Пока чат открыт, бот не будет реагировать на другие команды."
        )
        await message.bot.send_message(
            SUPPORT_GROUP_ID,
            f"👤 Новый тикет: @{username or 'Без username'} | {user_id}\nДиалог открыт.",
            message_thread_id=topic_id
        )
    await state.set_state(Support.waiting_for_message)

@router.message(Command("stop"), Support.waiting_for_message)
async def stop_support(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    ticket = await get_ticket(redis, user_id)
    if ticket and ticket["status"] == "open":
        await close_ticket(redis, user_id)
        log.log_message(f"❌ Пользователь @{username or 'Без username'} | id={user_id} закрыл чат поддержки", emoji="🔒")
        await message.answer("Диалог с поддержкой завершён. Бот снова доступен для скачивания видео.")
        await message.bot.send_message(
            SUPPORT_GROUP_ID,
            f"❌ Пользователь завершил диалог.",
            message_thread_id=ticket["topic_id"]
        )
    else:
        await message.answer("У вас нет открытого диалога с поддержкой.")
    await state.clear()

@router.message(Support.waiting_for_message)
async def forward_to_support(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    ticket = await get_ticket(redis, user_id)
    if not ticket or ticket["status"] != "open":
        await message.answer("У вас нет открытого диалога с поддержкой. Напишите /help для начала.")
        await state.clear()
        return
    topic_id = ticket["topic_id"]
    # Пересылаем сообщение в тему поддержки
    if message.text:
        await message.bot.send_message(
            SUPPORT_GROUP_ID,
            f"Сообщение от @{username or 'Без username'} | {user_id}:\n{message.text}",
            message_thread_id=topic_id
        )
    if message.photo:
        await message.bot.send_photo(
            SUPPORT_GROUP_ID,
            message.photo[-1].file_id,
            caption=f"Фото от @{username or 'Без username'} | {user_id}:\n{message.caption or ''}",
            message_thread_id=topic_id
        )
    log.log_message(f"✉️ Пользователь @{username or 'Без username'} | id={user_id} отправил сообщение в поддержку: {message.text or '[не текстовое сообщение]'}", emoji="📩")
