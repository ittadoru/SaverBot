
from aiogram import Router
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import ADMIN_ERROR
from states.ad_broadcast import AdBroadcastStates
import redis_db as redis
from redis_db.subscribers import get_all_subscribers
from utils import logger as log


router = Router()


@router.callback_query(lambda c: c.data == "ad_broadcast_start")
async def ad_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия на кнопку запуска рассылки — запрашиваем текст."""
    await callback.message.answer("Введите текст рекламной рассылки:")
    await state.set_state(AdBroadcastStates.waiting_text)



# Шаг 1: Получаем текст рассылки
@router.message(AdBroadcastStates.waiting_text)
async def process_ad_broadcast(message: Message, state: FSMContext):
    await state.update_data(broadcast_text=message.text)
    await message.answer("Добавить кнопку с ссылкой под рассылкой? (да/нет)")
    await state.set_state(AdBroadcastStates.waiting_button_choice)

# Шаг 2: Узнаём, нужна ли кнопка
@router.message(AdBroadcastStates.waiting_button_choice)
async def process_button_choice(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.lower() == "да":
        await message.answer("Введите текст кнопки:")
        await state.set_state(AdBroadcastStates.waiting_button_text)
    else:
        await send_broadcast(message, data["broadcast_text"])
        await state.clear()

# Шаг 3: Получаем текст кнопки
@router.message(AdBroadcastStates.waiting_button_text)
async def process_button_text(message: Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await message.answer("Введите ссылку для кнопки:")
    await state.set_state(AdBroadcastStates.waiting_button_url)

# Шаг 4: Получаем ссылку для кнопки и отправляем рассылку

@router.message(AdBroadcastStates.waiting_button_url)
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
    user_ids = await redis.r.smembers("users")
    subscribers = await get_all_subscribers()
    count_sent = 0

    for uid in user_ids:
        if str(uid) not in subscribers:
            try:
                await message.bot.send_message(uid, text, reply_markup=markup)
                count_sent += 1
            except Exception as e:
                await message.bot.send_message(ADMIN_ERROR, f"Ошибка отправки пользователю {uid}: {e}")
                log.log_error(f"Ошибка отправки пользователю {uid}: {e}")

    await message.reply(
        f"📢 Рекламная рассылка отправлена {count_sent} пользователям (не подписчикам)."
    )
    log.log_message(
        f"Рекламная рассылка отправлена {count_sent} пользователям (не подписчикам).",
        emoji="📢"
    )
