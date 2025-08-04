from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from states.broadcast import Broadcast
from utils.redis import r
from config import ADMINS
from utils import logger as log

router = Router()


@router.callback_query(F.data == "broadcast_start")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Запрос сообщения для рассылки (только для админов)."""
    if callback.from_user.id not in ADMINS:
        await callback.message.answer("⛔️ У вас нет доступа к рассылке.")
        return await callback.answer()

    await callback.message.answer("✉️ Пришлите сообщение для рассылки.")
    await state.set_state(Broadcast.waiting_for_message)
    await callback.answer()


@router.message(Broadcast.waiting_for_message)
async def handle_broadcast(message: Message, state: FSMContext):
    """Отправка сообщения всем пользователям из Redis."""
    current_state = await state.get_state()
    if current_state != Broadcast.waiting_for_message.state:
        return  # Состояние неактуально, игнорируем

    user_ids = await r.smembers("users")
    sent = 0

    log.log_message(
        f"Начата рассылка: {message.text or '[не текстовое сообщение]'}",
        emoji="📢"
    )

    for uid in user_ids:
        try:
            await message.send_copy(int(uid))
            sent += 1
        except Exception as e:
            log.log_error(f"Ошибка при отправке рассылки пользователю {uid}: {e}")

    log.log_message(
        f"Рассылка завершена. Отправлено {sent} пользователям.",
        emoji="📬"
    )

    await message.answer(f"✅ Отправлено {sent} пользователям.")
    await state.clear()


@router.callback_query(lambda c: c.data == "admin_menu")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки по кнопке."""
    await state.clear()
    await callback.message.answer("❌ Рассылка отменена.")
    await callback.answer()
