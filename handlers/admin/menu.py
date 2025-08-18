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
    builder.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="manage_users"))
    builder.row(InlineKeyboardButton(text="🎟 Промокоды", callback_data="promocode_menu"))
    builder.row(InlineKeyboardButton(text="📦 Логи", callback_data="get_logs"))
    builder.row(InlineKeyboardButton(text="📊 Таблицы", callback_data="export_table_menu"))
    builder.row(InlineKeyboardButton(text="💳 Тарифы", callback_data="tariff_menu"))
    builder.row(InlineKeyboardButton(text="📢 Каналы", callback_data="channels_menu"))
    builder.row(InlineKeyboardButton(text="🗑️ Очистить downloads", callback_data="clear_downloads"))
    builder.row(
        InlineKeyboardButton(text="📨 Обычная", callback_data="broadcast_start"),
        InlineKeyboardButton(text="💸 Реклама", callback_data="ad_broadcast_start"),
        InlineKeyboardButton(text="🎯 Новички", callback_data="trial_broadcast_start")
    )
    return builder.as_markup()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Обрабатывает команду /admin, отображая главное меню для администратора."""
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔️ У вас нет доступа к этой команде.")

    await message.answer(
        "🔐 <b>Админ-панель</b>\n\nВыберите нужный раздел:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )


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
    builder.row(InlineKeyboardButton(text="🔍 Поиск", callback_data="user_history_start"))
    builder.row(InlineKeyboardButton(text="🗑️ Удалить всех", callback_data="delete_all_users"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    await callback.message.edit_text(
        "👥 <b>Пользователи</b>\n\nВыберите действие:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    """Обрабатывает кнопку 'Назад', возвращая к главной админ-панели."""
    await callback.message.edit_text(
        "🔐 <b>Админ-панель</b>\n\nВыберите нужный раздел:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# Обработчик для удаления всех файлов из downloads
from utils.delete_downloads import delete_all_files_in_downloads

@router.callback_query(F.data == "clear_downloads")
async def clear_downloads_handler(callback: CallbackQuery):
    deleted = delete_all_files_in_downloads()
    await callback.answer()
    await callback.message.answer(f"🗑️ Удалено файлов из downloads: <b>{deleted}</b>", parse_mode="HTML")