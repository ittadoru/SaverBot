from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from config import ADMINS

router = Router()


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главной админ-панели."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="manage_users")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="promocode_menu")],
        [InlineKeyboardButton(text="📦 Экспорт логов", callback_data="export_logs")],
        [InlineKeyboardButton(text="💳 Управление тарифами", callback_data="tariff_menu")],
        [
            InlineKeyboardButton(text="📨 Обычная рассылка", callback_data="broadcast_start"),
            InlineKeyboardButton(text="💸 Рекламная рассылка", callback_data="ad_broadcast_start")
        ],
        [
            InlineKeyboardButton(text="📈 Топ за 7 дней", callback_data="top_week"),
            InlineKeyboardButton(text="🏅 Топ за все время", callback_data="top_all")
        ],
        [InlineKeyboardButton(text="🗑 Удалить все видео", callback_data="delete_videos")]
    ])


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Обработка команды /admin — отображение главного меню для админа."""
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔️ У вас нет доступа к этой команде.")

    await message.answer("🔐 Админ-панель", reply_markup=get_admin_menu_keyboard())


@router.callback_query(lambda c: c.data == "promocode_menu")
async def promocode_menu(callback: CallbackQuery):
    """Меню управления промокодами."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить промокод", callback_data="add_promocode")],
        [InlineKeyboardButton(text="➖ Удалить промокод", callback_data="remove_promocode")],
        [InlineKeyboardButton(text="🎟 Все промокоды", callback_data="all_promocodes")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
    ])
    await callback.message.edit_text("Меню промокодов:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "manage_users")
async def manage_users_menu(callback: CallbackQuery):
    """Меню управления пользователями."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="all_users")],
        [InlineKeyboardButton(text="🔍 История пользователя", callback_data="user_history_start")],
        [InlineKeyboardButton(text="🗑️ Удалить всех пользователей", callback_data="delete_all_users")],
        [InlineKeyboardButton(text="♻️ Сбросить busy-флаги", callback_data="reset_busy_flags")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
    ])
    await callback.message.edit_text("Выберите действие:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "export_logs")
async def export_logs_menu(callback: CallbackQuery):
    """Меню экспорта логов."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Последние", callback_data="last_logs")],
        [InlineKeyboardButton(text="📅 По дате", callback_data="custom_logs")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
    ])
    await callback.message.edit_text("Выберите действие:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    """Возврат к главной админ-панели."""
    await callback.message.edit_text("🔐 Админ-панель", reply_markup=get_admin_menu_keyboard())
    await callback.answer()
