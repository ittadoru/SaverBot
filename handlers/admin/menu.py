"""Главное меню админа: статистика, пользователи, тарифы, каналы, базовая рассылка."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from utils.delete_downloads import delete_all_files_in_downloads

from config import ADMINS


router = Router()

def get_admin_menu_keyboard():
    """Формирует и возвращает клавиатуру главной админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
        InlineKeyboardButton(text="👥 Пользователи", callback_data="manage_users"),
    )
    builder.row(
        InlineKeyboardButton(text="💳 Тарифы", callback_data="tariff_menu"),
        InlineKeyboardButton(text="📢 Каналы", callback_data="channels_menu"),
        InlineKeyboardButton(text="📨 Рассылка", callback_data="broadcast_start"),
    )
    builder.row(InlineKeyboardButton(text="🗑️ Очистить downloads", callback_data="clear_downloads"))
    return builder.as_markup()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Обрабатывает команду /admin, отображая главное меню для администратора."""
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔️ У вас нет доступа к этой команде.")

    await message.answer(
    "<b>🔐 Админ-панель</b>\n\n"
    "Добро пожаловать! Здесь вы можете управлять пользователями, тарифами, каналами и рассылками.\n"
    "\nВыберите нужный раздел ниже:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "manage_users")
async def manage_users_entry(callback: CallbackQuery):
    """Перехватывает вход в меню управления пользователями и вызывает основную функцию отображения."""
    from .users import manage_users_menu
    await manage_users_menu(callback)


@router.callback_query(F.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    """Обрабатывает кнопку 'Назад', возвращая к главной админ-панели."""
    await callback.message.edit_text(
    "<b>🔐 Админ-панель</b>\n\n"
    "Добро пожаловать! Здесь вы можете управлять пользователями, тарифами, каналами и рассылками.\n"
    "\nВыберите нужный раздел ниже:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "clear_downloads")
async def clear_downloads_handler(callback: CallbackQuery):
    """Очищает папку downloads и сообщает количество удалённых файлов."""
    deleted = await delete_all_files_in_downloads()
    await callback.answer()
    await callback.message.answer(f"🗑️ Удалено файлов из downloads: <b>{deleted}</b>", parse_mode="HTML")
