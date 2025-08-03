from aiogram.filters import CommandObject
from aiogram import types, Router
from aiogram.filters import Command
from config import ADMINS
from utils.redis import r, get_user_links
from aiogram.fsm.context import FSMContext
from states.history import HistoryStates


router = Router()

@router.callback_query(lambda c: c.data == "user_history_start")
async def show_user_history(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return await callback.message.answer("⛔️ У вас нет доступа к этой команде.")
    await state.set_state(HistoryStates.waiting_for_id_or_username)
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_users")]
        ]
    )
    await callback.message.edit_text("⚠️ Введите ID или username пользователя:", reply_markup=keyboard)
    await callback.answer()

@router.message(HistoryStates.waiting_for_id_or_username)
async def process_id_or_username(message: types.Message, state: FSMContext):
    print("FSM обработчик вызван, текст:", message.text)  # Для отладки
    arg = message.text.strip()
    user_id = None
    if arg.isdigit():
        user_id = int(arg)
    else:
        username = arg.lstrip("@").lower()
        user_ids = await r.smembers("users")
        for uid in user_ids:
            data = await r.hgetall(f"user:{uid}")
            if data.get("username", "").lower() == username:
                user_id = int(uid)
                break
    if user_id is None:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_users")]
            ]
        )
        await message.answer("❌ Пользователь не найден.", reply_markup=keyboard)
        await state.clear()
        return
    user_data = await r.hgetall(f"user:{user_id}")
    if not user_data:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_users")]
            ]
        )
        await message.answer("❌ Данные пользователя не найдены.", reply_markup=keyboard)
        await state.clear()
        return
    links = await get_user_links(user_id)
    name = user_data.get("first_name", "")
    username = user_data.get("username", "")
    user_info = f"<b>👤 Пользователь:</b>\n\n"
    user_info += f"ID: <code>{user_id}</code>\n"
    user_info += f"Имя: {name}\n"

    if username:
        user_info += f"Username: @{username}\n"
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_users")]
        ]
    )
    if not links:
        await message.answer(user_info + "\nℹ️ У пользователя нет недавних ссылок.", parse_mode="HTML", reply_markup=keyboard)
        await state.clear()
        return
    
    links_text = "\n".join([f"<pre>{link}</pre>" for link in links])
    full_text = user_info + "\n\n<b>🔗 Последние ссылки:</b>\n\n" + links_text
    await message.answer(full_text, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()
