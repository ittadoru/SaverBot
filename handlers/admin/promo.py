from aiogram import Router, types
from aiogram.types import CallbackQuery
from utils import redis, logger as log
from config import ADMINS
from states.promo import PromoStates
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State

router = Router()

@router.callback_query(lambda c: c.data == "add_promocode")
async def add_promocode_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите промокод и срок действия (дней) через пробел.\nПример: CODE123 30")
    await state.set_state(PromoStates.add)
    await callback.answer()


@router.message(PromoStates.add)
async def process_add_promocode(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    data = await state.get_data()
    attempts = data.get("add_attempts", 0)
    if message.text:
        parts = message.text.strip().split()
        if len(parts) == 2 and parts[1].isdigit():
            code, days = parts[0], int(parts[1])
            await redis.add_promocode(code, days)
            log.log_message(f"Добавлен промокод: {code} на {days} дней админом {message.from_user.username} ({message.from_user.id})", emoji="🎟")
            await message.answer(f"Промокод {code} на {days} дней добавлен.")
            await state.clear()
        else:
            attempts += 1
            if attempts < 2:
                await state.update_data(add_attempts=attempts)
                await message.answer("Неверный формат. Пример: CODE123 30\nПопробуйте ещё раз.")
            else:
                await message.answer("Вы дважды ошиблись с форматом. Операция отменена.")
                await state.clear()

@router.callback_query(lambda c: c.data == "remove_promocode")
async def remove_promocode_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите промокод для удаления:")
    await state.set_state(PromoStates.remove)
    await callback.answer()

@router.message(PromoStates.remove)
async def process_remove_promocode(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    code = message.text.strip()
    promocodes = await redis.get_all_promocodes()
    if code in promocodes:
        await redis.remove_promocode(code)
        log.log_message(f"Удалён промокод: {code} админом {message.from_user.username} ({message.from_user.id})", emoji="🗑")
        text = f"Промокод {code} удалён."
    else:
        text = f"Промокод {code} не найден."
    await message.answer(text)
    await state.clear()

@router.callback_query(lambda c: c.data == "all_promocodes")
async def show_all_promocodes(callback: CallbackQuery):
    promocodes = await redis.get_all_promocodes()
    if promocodes:
        text = "<b>Все промокоды:</b>\n" + "\n".join([f"{k}: {v} дней" for k, v in promocodes.items()])
    else:
        text = "Нет активных промокодов."
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
