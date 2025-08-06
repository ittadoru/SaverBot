from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from redis_db.subscribers import activate_promocode
from redis_db import r
from utils import logger as log
from states.promo import PromoStates

router = Router()

@router.callback_query(lambda c: c.data == "promo")
async def promo_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Пожалуйста, введите промокод для активации подписки:")
    await state.set_state(PromoStates.user)

@router.message(PromoStates.user)
async def process_user_promocode(message: types.Message, state: FSMContext):
    code = message.text.strip()
    duration = await r.hget("promocodes", code)
    result = await activate_promocode(message.from_user.id, code)
    
    if result and duration:
        log.log_message(
            f"Пользователь {message.from_user.username} ({message.from_user.id}) активировал промокод {code}",
            emoji="✅"
        )
        await message.answer(f"🎉 Промокод успешно активирован! Ваша подписка продлена на {duration} дней.")
    else:
        log.log_message(
            f"Пользователь {message.from_user.username} ({message.from_user.id}) попытался активировать несуществующий или уже использованный промокод {code}",
            emoji="❌"
        )
        await message.answer("⚠️ Промокод не найден или уже был использован. Проверьте правильность и попробуйте снова.")
    
    await state.clear()
