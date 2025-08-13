from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states.broadcast import Broadcast
from redis_db import r
from config import ADMIN_ERROR
from utils import logger as log

router = Router()


@router.callback_query(F.data == "broadcast_start")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Запрос сообщения для рассылки (только для админов)."""
    await callback.message.answer("✉️ Пришлите сообщение для рассылки.")
    await state.set_state(Broadcast.waiting_for_message)
    await callback.answer()



# Шаг 1: Получаем текст рассылки
@router.message(Broadcast.waiting_for_message)
async def handle_broadcast(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != Broadcast.waiting_for_message.state:
        return
    await state.update_data(broadcast_text=message.text)
    await message.answer("Добавить кнопку с ссылкой под рассылкой? (да/нет)")
    await state.set_state(Broadcast.waiting_button_choice)

# Шаг 2: Узнаём, нужна ли кнопка
@router.message(Broadcast.waiting_button_choice)
async def process_button_choice(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.lower() == "да":
        await message.answer("Введите текст кнопки:")
        await state.set_state(Broadcast.waiting_button_text)
    else:
        await send_broadcast(message, data["broadcast_text"])
        await state.clear()

# Шаг 3: Получаем текст кнопки
@router.message(Broadcast.waiting_button_text)
async def process_button_text(message: Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await message.answer("Введите ссылку для кнопки:")
    await state.set_state(Broadcast.waiting_button_url)

# Шаг 4: Получаем ссылку для кнопки и отправляем рассылку

@router.message(Broadcast.waiting_button_url)
async def process_button_url(message: Message, state: FSMContext):
    data = await state.get_data()
    button_text = data["button_text"]
    button_url = message.text.strip()
    text = data["broadcast_text"]
    # Проверка на валидность ссылки
    if not (button_url.startswith("http://") or button_url.startswith("https://")):
        await message.answer("❗️ Пожалуйста, введите корректную ссылку, начинающуюся с http:// или https://")
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=button_text, url=button_url)]]
    )
    try:
        await send_broadcast(message, text, markup)
    except Exception as e:
        await message.answer(f"❗️ Ошибка при отправке рассылки: {e}")
    await state.clear()

# Функция рассылки
async def send_broadcast(message: Message, text: str, markup: InlineKeyboardMarkup = None):
    user_ids = await r.smembers("users")
    sent = 0

    log.log_message(
        f"Начата рассылка: {text or '[не текстовое сообщение]'}",
        emoji="📢"
    )

    for uid in user_ids:
        try:
            await message.bot.send_message(int(uid), text, reply_markup=markup)
            sent += 1
        except Exception as e:
            # Ловим TelegramBadRequest и другие ошибки
            await message.bot.send_message(
                ADMIN_ERROR, f"Ошибка при отправке рассылки пользователю {uid}: {e}"
            )
            log.log_error(f"Ошибка при отправке рассылки пользователю {uid}: {e}")

    log.log_message(
        f"Рассылка завершена. Отправлено {sent} пользователям.",
        emoji="📬"
    )

    await message.answer(f"✅ Отправлено {sent} пользователям.")


@router.callback_query(lambda c: c.data == "admin_menu")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки по кнопке."""
    await state.clear()
    log.log_message("Рассылка отменена по запросу администратора.", emoji="❌")
    await callback.message.answer("❌ Рассылка отменена.")
    await callback.answer()
