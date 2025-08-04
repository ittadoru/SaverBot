from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from utils import redis, logger as log
from states.promo import PromoStates

router = Router()

@router.message(Command("promo"))
async def promo_start(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, введите промокод для активации подписки:")
    await state.set_state(PromoStates.user)

@router.message(PromoStates.user)
async def process_user_promocode(message: types.Message, state: FSMContext):
    code = message.text.strip()
    duration = await redis.r.hget("promocodes", code)
    result = await redis.activate_promocode(message.from_user.id, code)
    
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
