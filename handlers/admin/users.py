from aiogram import types, Router
from config import ADMINS
from utils.redis import r
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

# Кнопка "Все пользователи" с отметкой подписчик/нет
@router.callback_query(lambda c: c.data == "all_users")
async def list_users(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return await callback.message.answer("⛔️ У вас нет доступа к этой команде.")

    user_ids = list(await r.smembers("users"))
    if not user_ids:
        return await callback.message.answer("Пользователей пока нет.")

    user_ids.sort()
    page = 1
    per_page = 20
    total_pages = (len(user_ids) + per_page - 1) // per_page
    users_page = user_ids[(page - 1)*per_page : page*per_page]

    text = "👥 <b>Пользователи:</b>\n\n"
    subs_ids = set(await r.smembers("subscribers"))
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
        reply_markup=get_users_keyboard(page, total_pages)
    )
    await callback.answer()


def get_users_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️", callback_data=f"users_page:{page - 1}" if page > 1 else "noop"),
            InlineKeyboardButton(text=f"{page} / {total_pages}", callback_data="noop"),
            InlineKeyboardButton(text="▶️", callback_data=f"users_page:{page + 1}" if page < total_pages else "noop"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_users")]
    ])

# Пагинация
@router.callback_query(lambda c: c.data.startswith("users_page:"))
async def paginate_users(callback: types.CallbackQuery):
    page = int(callback.data.split(":")[1])
    user_ids = list(await r.smembers("users"))
    user_ids.sort()
    per_page = 20
    total_pages = (len(user_ids) + per_page - 1) // per_page
    if page < 1 or page > total_pages:
        return await callback.answer("Нет такой страницы")
    users_page = user_ids[(page - 1)*per_page : page*per_page]
    text = "👥 <b>Пользователи:</b>\n\n"
    subs_ids = set(await r.smembers("subscribers"))
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
        reply_markup=get_users_keyboard(page, total_pages)
    )
    await callback.answer()
