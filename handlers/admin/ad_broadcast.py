from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config import ADMIN_ERROR
from states.ad_broadcast import AdBroadcastStates
import redis_db as redis
from redis_db.subscribers import get_all_subscribers
from utils import logger as log

import traceback

router = Router()


@router.callback_query(lambda c: c.data == "ad_broadcast_start")
async def ad_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия на кнопку запуска рассылки — запрашиваем текст."""
    await callback.message.answer("Введите текст рекламной рассылки:")
    await state.set_state(AdBroadcastStates.waiting_text)


@router.message(AdBroadcastStates.waiting_text)
async def process_ad_broadcast(message: Message, state: FSMContext):
    """Отправка рекламной рассылки всем пользователям, кроме подписчиков."""
    user_ids = await redis.r.smembers("users")
    subscribers = await get_all_subscribers()
    count_sent = 0

    for uid in user_ids:
        if str(uid) not in subscribers:
            try:
                await message.bot.send_message(uid, message.text)
                count_sent += 1
            except Exception as e:
                await message.bot.send_message(ADMIN_ERROR, f"Ошибка отправки пользователю {uid}: {e}")
                log.log_error(f"Ошибка отправки пользователю {uid}: {e}")

    await message.reply(
        f"📢 Рекламная рассылка отправлена {count_sent} пользователям (не подписчикам)."
    )
    log.log_message(
        f"Рекламная рассылка отправлена {count_sent} пользователям (не подписчикам).",
        emoji="📢"
    )
