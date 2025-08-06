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
                print(f"Ошибка отправки пользователю {uid}: {e}")

    try:
        await message.reply(
            f"Рекламная рассылка отправлена {count_sent} пользователям (не подписчикам)."
        )
        log.log_message(
            f"Рекламная рассылка отправлена {count_sent} пользователям (не подписчикам).",
            emoji="📢"
        )
    except Exception as e:
        # Логирование и уведомление об ошибке при отправке отчёта
        error_text = f"Ошибка: {e}"
        full_trace = traceback.format_exc()

        log.log_error(error_text)
        log.log_error(full_trace)

        try:
            await message.bot.send_message(
                ADMIN_ERROR,
                f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                parse_mode="HTML"
            )
        except Exception as send_err:
            log.log_error(f"Не удалось отправить ошибку админу: {send_err}")

    await state.clear()
