from aiogram import Router, types
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from utils import redis

from states.ad_broadcast import AdBroadcastStates

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
        try:
            await message.answer(f"Рекламная рассылка отправлена {count_sent} пользователям (не подписчикам).")
        except Exception:
            try:
                await message.bot.send_message(message.from_user.id, f"❗️ Ошибка отправки результата рассылки: {str(e)}")
            except Exception:
                pass
    await state.clear()
