from aiogram import types, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMINS
from redis_db import r

router = Router()


@router.callback_query(lambda c: c.data == "all_users")
async def list_users(callback: types.CallbackQuery):
    """
    Показывает список всех пользователей с отметкой о подписке.
    Отображает первую страницу с пагинацией.
    """
    if callback.from_user.id not in ADMINS:
        await callback.message.answer("⛔️ У вас нет доступа к этой команде.")
        return

    user_ids = list(await r.smembers("users"))
    if not user_ids:
        await callback.message.answer("Пользователей пока нет.")
        return

    user_ids.sort()
    page = 1
    per_page = 20
    total_pages = (len(user_ids) + per_page - 1) // per_page

    users_page = user_ids[(page - 1) * per_page : page * per_page]
    subs_ids = set(await r.smembers("subscribers"))

    text = "👥 <b>Пользователи:</b>\n\n"
    for uid in users_page:
        user_data = await r.hgetall(f"user:{uid}")
        username = user_data.get("username", "")
        name = user_data.get("first_name", "")
        # Отмечаем подписчиков 💎, остальных ❌
        is_sub = "💎" if str(uid) in subs_ids else "❌"
        text += f"{is_sub} {uid} — {name}"
        if username:
            text += f" (@{username})"
        text += "\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_users_keyboard(page, total_pages),
    )
    await callback.answer()


def get_users_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с кнопками для навигации по страницам и кнопкой назад.
    """
    buttons = [
        InlineKeyboardButton(
            text="◀️", callback_data=f"users_page:{page - 1}" if page > 1 else "noop"
        ),
        InlineKeyboardButton(text=f"{page} / {total_pages}", callback_data="noop"),
        InlineKeyboardButton(
            text="▶️", callback_data=f"users_page:{page + 1}" if page < total_pages else "noop"
        ),
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons,
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_users")]
        ]
    )
# Удаление всех пользователей
@router.callback_query(lambda c: c.data == "delete_all_users")
async def delete_all_users_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("⛔️ У вас нет доступа к этой команде.", show_alert=True)
        return
    user_ids = list(await r.smembers("users"))
    for uid in user_ids:
        await r.srem("users", uid)
        await r.srem("subscribers", uid)
        await r.delete(f"user:{uid}")
        await r.delete(f"user:busy:{uid}")
    await callback.answer(f"Все пользователи удалены", show_alert=True)

# Сброс busy-флагов всем пользователям
@router.callback_query(lambda c: c.data == "reset_busy_flags")
async def reset_busy_flags(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.message.answer("⛔️ У вас нет доступа к этой команде.")
        return

    user_ids = list(await r.smembers("users"))
    count = 0
    for uid in user_ids:
        key = f"user:busy:{uid}"
        if await r.exists(key):
            await r.delete(key)
            count += 1
    await callback.answer(f"Сброшено busy-флагов: {count}", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("users_page:"))
async def paginate_users(callback: types.CallbackQuery):
    """
    Обрабатывает переключение страниц списка пользователей.
    """
    page = int(callback.data.split(":")[1])

    user_ids = list(await r.smembers("users"))
    user_ids.sort()

    per_page = 20
    total_pages = (len(user_ids) + per_page - 1) // per_page

    if page < 1 or page > total_pages:
        await callback.answer("Нет такой страницы", show_alert=True)
        return

    users_page = user_ids[(page - 1) * per_page : page * per_page]
    subs_ids = set(await r.smembers("subscribers"))

    text = "👥 <b>Пользователи:</b>\n\n"
    for uid in users_page:
        user_data = await r.hgetall(f"user:{uid}")
        username = user_data.get("username", "")
        name = user_data.get("first_name", "")
        is_sub = "💎" if str(uid) in subs_ids else "❌"
        text += f"{is_sub} {uid} — {name}"
        if username:
            text += f" (@{username})"
        text += "\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_users_keyboard(page, total_pages),
    )
    await callback.answer()
