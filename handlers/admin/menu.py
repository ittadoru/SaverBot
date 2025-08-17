"""Главное меню админа: доступ к статистике, пользователям, промокодам, логам, экспорту, тарифам и рассылкам."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

from config import ADMINS

router = Router()


def get_admin_menu_keyboard():
    """Формирует и возвращает клавиатуру главной админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="stats"))
    builder.row(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="manage_users"))
    builder.row(InlineKeyboardButton(text="🎟 Промокоды", callback_data="promocode_menu"))
    builder.row(InlineKeyboardButton(text="📦 Выгрузить логи", callback_data="get_logs"))
    builder.row(InlineKeyboardButton(text="📊 Экспорт таблицы", callback_data="export_table_menu"))
    builder.row(InlineKeyboardButton(text="💳 Управление тарифами", callback_data="tariff_menu"))
    builder.row(InlineKeyboardButton(text="📢 Каналы", callback_data="channels_menu"))
    builder.row(
        InlineKeyboardButton(text="📨 Обычная", callback_data="broadcast_start"),
        InlineKeyboardButton(text="💸 Рекламная", callback_data="ad_broadcast_start"),
        InlineKeyboardButton(text="🎯 Неплатившие", callback_data="trial_broadcast_start")
    )
    return builder.as_markup()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Обрабатывает команду /admin, отображая главное меню для администратора."""
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔️ У вас нет доступа к этой команде.")

    await message.answer("🔐 Админ-панель", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "promocode_menu")
async def promocode_menu_entry(callback: CallbackQuery):
    """Перехватывает вход в меню промокодов и вызывает основную функцию отображения."""
    from .promo import show_promo_menu
    await show_promo_menu(callback)



@router.callback_query(F.data == "manage_users")
async def manage_users_menu(callback: CallbackQuery):
    """Отображает меню управления пользователями."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Все пользователи", callback_data="all_users"))
    builder.row(InlineKeyboardButton(text="🔍 Данные пользователя", callback_data="user_history_start"))
    builder.row(InlineKeyboardButton(text="🗑️ Удалить всех пользователей", callback_data="delete_all_users"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    await callback.message.edit_text("Выберите действие:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    """Обрабатывает кнопку 'Назад', возвращая к главной админ-панели."""
    await callback.message.edit_text("🔐 Админ-панель", reply_markup=get_admin_menu_keyboard())
    await callback.answer()
