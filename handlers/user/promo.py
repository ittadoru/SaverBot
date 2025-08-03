from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from utils import redis, logger as log
from states.promo import PromoStates

router = Router()

@router.message(Command("promo"))
async def promo_start(message: types.Message, state: FSMContext):
    await message.answer("Введите промокод:")
    await state.set_state(PromoStates.user)

@router.message(PromoStates.user)
async def process_user_promocode(message: types.Message, state: FSMContext):
    code = message.text.strip()
    # Получаем срок действия промокода
    duration = await redis.r.hget("promocodes", code)
    result = await redis.activate_promocode(message.from_user.id, code)
    if result and duration:
        log.log_message(f"Пользователь {message.from_user.username} ({message.from_user.id}) активировал промокод {code}", emoji="✅")
        await message.answer(f"Промокод успешно активирован! Вы получили подписку на {duration} дней.")
    else:
        log.log_message(f"Пользователь {message.from_user.username} ({message.from_user.id}) попытался активировать несуществующий промокод {code}", emoji="❌")
        await message.answer("Промокод не найден или уже использован.")
    await state.clear()
