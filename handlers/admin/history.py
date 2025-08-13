from aiogram import types, Router
from aiogram.fsm.context import FSMContext

from redis_db import r
from redis_db.users import get_user_links
from states.history import HistoryStates
from datetime import datetime
from utils import logger as log

router = Router()


@router.callback_query(lambda c: c.data == "user_history_start")
async def show_user_history(callback: types.CallbackQuery, state: FSMContext):
    """Запрос ID или username для просмотра истории пользователя (только для админов)."""
    await state.set_state(HistoryStates.waiting_for_id_or_username)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_users")]
        ]
    )

    await callback.message.edit_text(
        "⚠️ Введите ID или username пользователя:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.message(HistoryStates.waiting_for_id_or_username)
async def process_id_or_username(message: types.Message, state: FSMContext):
    """Обработка введённого ID или username, поиск истории ссылок пользователя."""
    arg = message.text.strip()
    user_id = None

    if arg.isdigit():
        user_id = int(arg)
    else:
        # Поиск по username (без @, в нижнем регистре)
        username = arg.lstrip("@").lower()
        user_ids = await r.smembers("users")

        for uid in user_ids:
            data = await r.hgetall(f"user:{uid}")
            if data.get("username", "").lower() == username:
                user_id = int(uid)
                break

    # Если пользователь не найден
    if user_id is None:
        await message.answer("❌ Пользователь не найден.")
        await state.clear()
        return

    # Получение информации о пользователе
    user_data = await r.hgetall(f"user:{user_id}")
    expire_timestamp = await r.get(f"subscriber:expire:{user_id}")
    if expire_timestamp:
        expire_timestamp = int(expire_timestamp)
        expiry_date = datetime.fromtimestamp(expire_timestamp)
        if expiry_date > datetime.now():
            subscription_status = f"✅ Подписка активна до <b>{expiry_date.strftime('%d.%m.%Y %H:%M')}</b>"
        else:
            subscription_status = "❌ Подписка истекла"
    else:
        subscription_status = "❌ Подписка не активна"

    links = await get_user_links(user_id)
    name = user_data.get("first_name", "")
    username = user_data.get("username", "")

    user_info = "<b>👤 Пользователь:</b>\n\n"
    user_info += f"ID: <code>{user_id}</code>\n"
    user_info += f"Имя: {name}\n"
    user_info += f"{subscription_status}\n"
    if username:
        user_info += f"Username: @{username}\n"

    # Клавиатура: удалить пользователя и назад
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=f"🗑️ Удалить пользователя", callback_data=f"delete_user:{user_id}")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_users")]
        ]
    )

    if not links:
        await message.answer(
            user_info + "\nℹ️ У пользователя нет недавних ссылок.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await state.clear()
        return

    # Формирование текста с последними ссылками
    links_text = "\n".join([f"<pre>{link}</pre>" for link in links[:5]])
    full_text = user_info + "\n\n<b>🔗 Последние ссылки:</b>\n\n" + links_text

    log.log_message(f"Админ просмотрел историю пользователя {user_id}", emoji="📜")
    await message.answer(full_text, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()

@router.callback_query(lambda c: c.data.startswith("delete_user:"))
async def delete_user_callback(callback: types.CallbackQuery):
    uid = callback.data.split(":")[1]

    # Удаляем пользователя из всех связанных структур
    await r.srem("users", uid)
    await r.srem("subscribers", uid)
    await r.delete(f"user:{uid}")
    await r.delete(f"user:busy:{uid}")

    await callback.message.answer(f"Пользователь {uid} удалён", show_alert=True)
    log.log_message(f"Админ удалил пользователя {uid}", emoji="🗑️")
