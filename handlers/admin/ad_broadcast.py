from aiogram import Router, types
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from utils import redis
from config import ADMIN_ERROR
from states.ad_broadcast import AdBroadcastStates
from utils import logger as log
router = Router()


@router.callback_query(lambda c: c.data == "ad_broadcast_start")
async def ad_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите текст рекламной рассылки:")
    await state.set_state(AdBroadcastStates.waiting_text)

@router.message(AdBroadcastStates.waiting_text)
async def process_ad_broadcast(message: types.Message, state: FSMContext):
    user_ids = await redis.r.smembers("users")
    subscribers = await redis.get_all_subscribers()
    count_sent = 0
    for uid in user_ids:
        if str(uid) not in subscribers:
            try:
                await message.bot.send_message(uid, message.text)
                count_sent += 1
            except Exception as e:
                print(f"Ошибка отправки пользователю {uid}: {e}")
    try:
        await message.reply(f"Рекламная рассылка отправлена {count_sent} пользователям (не подписчикам).")
    except Exception as e:
        import traceback
        error_text = f"Ошибка: {e}"
        full_trace = traceback.format_exc()
        log.log_error(error_text)
        log.log_error(full_trace)
        # Отправка сообщения админу (замените на нужный ID)
        try:
            await message.bot.send_message(
                ADMIN_ERROR,
                f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                parse_mode="HTML"
            )
        except Exception as send_err:
            log.log_error(f"Не удалось отправить ошибку админу: {send_err}")

    await state.clear()
