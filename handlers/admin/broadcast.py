from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from states.broadcast import Broadcast
from utils.redis import r
from config import ADMINS

router = Router()

@router.callback_query(F.data == "broadcast_start")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        await callback.message.answer("⛔️ У вас нет доступа к рассылке.")
        return await callback.answer()
    await callback.message.answer("✉️ Пришлите сообщение для рассылки.")
    await state.set_state(Broadcast.waiting_for_message)
    await callback.answer()

@router.message(Broadcast.waiting_for_message)
async def handle_broadcast(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != Broadcast.waiting_for_message.state:
        # Неактивно, игнорируем
        return
    user_ids = await r.smembers("users")
    sent = 0
    for uid in user_ids:
        try:
            await message.send_copy(int(uid))
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ Отправлено {sent} пользователям.")
    await state.clear()
@router.callback_query(lambda c: c.data == "admin_menu")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Рассылка отменена.")
    await callback.answer()