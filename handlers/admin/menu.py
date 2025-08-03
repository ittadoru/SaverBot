from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from config import ADMINS

router = Router()

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔️ У вас нет доступа к этой команде.")
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [types.InlineKeyboardButton(text="👥 Управление пользователями", callback_data="manage_users")],
        [types.InlineKeyboardButton(text="🎟 Промокоды", callback_data="promocode_menu")],
        [types.InlineKeyboardButton(text="📦 Экспорт логов", callback_data="export_logs")],
        [
            types.InlineKeyboardButton(text="📨 Обычная рассылка", callback_data="broadcast_start"),
            types.InlineKeyboardButton(text="📰 Рекламная рассылка", callback_data="ad_broadcast_start")
        ],
        [
            types.InlineKeyboardButton(text="📈 Топ за 7 дней", callback_data="top_week"), 
            types.InlineKeyboardButton(text="🏅 Топ за все время", callback_data="top_all")
        ],
        [types.InlineKeyboardButton(text="🗑 Удалить все видео", callback_data="delete_videos")]
    ])

    await message.answer("🔐 Админ-панель", reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "promocode_menu")
async def promocode_menu(callback: CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➕ Добавить промокод", callback_data="add_promocode")],
        [types.InlineKeyboardButton(text="➖ Удалить промокод", callback_data="remove_promocode")],
        [types.InlineKeyboardButton(text="📋 Все промокоды", callback_data="all_promocodes")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
    ])
    await callback.message.edit_text("Меню промокодов:", reply_markup=keyboard)
    await callback.answer()
    

@router.callback_query(lambda c: c.data == "manage_users")
async def manage_users_menu(callback: CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📋 Все пользователи", callback_data="all_users")],
        [types.InlineKeyboardButton(text="🔍 История пользователя", callback_data="user_history_start")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
    ])
    await callback.message.edit_text("Выберите действие:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "export_logs")
async def export_logs_menu(callback: CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📋 Последние", callback_data="last_logs")],
        [types.InlineKeyboardButton(text="📅 По дате", callback_data="custom_logs")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
    ])
    await callback.message.edit_text("Выберите действие:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [types.InlineKeyboardButton(text="👥 Управление пользователями", callback_data="manage_users")],
        [types.InlineKeyboardButton(text="🎟 Промокоды", callback_data="promocode_menu")],
        [types.InlineKeyboardButton(text="📦 Экспорт логов", callback_data="export_logs")],
        [
            types.InlineKeyboardButton(text="📨 Обычная рассылка", callback_data="broadcast_start"),
            types.InlineKeyboardButton(text="📰 Рекламная рассылка", callback_data="ad_broadcast_start")
        ],
        [
            types.InlineKeyboardButton(text="📈 Топ за 7 дней", callback_data="top_week"), 
            types.InlineKeyboardButton(text="🏅 Топ за все время", callback_data="top_all")
        ],
        [types.InlineKeyboardButton(text="🗑 Удалить все видео", callback_data="delete_videos")]
    ])
    await callback.message.edit_text("🔐 Админ-панель", reply_markup=keyboard)
    await callback.answer()
