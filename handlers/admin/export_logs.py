"""Экспорт логов: список доступных файлов и отправка выбранного админу."""

import logging
import os
import asyncio
import re
from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

LOG_DIR = "logs"


class LogCallback(CallbackData, prefix="log_select"):
    """Фабрика колбэков для выбора конкретного файла лога."""
    filename: str


router = Router()

async def get_current_log():
    """Возвращает имя текущего лога, если есть."""
    if not await asyncio.to_thread(os.path.exists, LOG_DIR):
        return None
    files = await asyncio.to_thread(os.listdir, LOG_DIR)
    return "bot.log" if "bot.log" in files else None

async def get_archived_logs():
    """Возвращает отсортированный список архивных логов формата bot_YYYY-MM-DD.log."""
    if not await asyncio.to_thread(os.path.exists, LOG_DIR):
        return []
    files = await asyncio.to_thread(os.listdir, LOG_DIR)
    log_pattern = re.compile(r"^bot_(\d{4})-(\d{2})-(\d{2})\.log$")
    archived_logs = sorted(
        [f for f in files if log_pattern.match(f)],
        reverse=True
    )
    return archived_logs

@router.callback_query(F.data == "get_logs")
async def show_log_main_menu(callback: CallbackQuery):
    """Показывает главное меню экспорта логов: текущий лог и архивные логи."""
    builder = InlineKeyboardBuilder()
    current_log = await get_current_log()
    if current_log:
        builder.button(
            text="📄 Текущий лог",
            callback_data=LogCallback(filename=current_log).pack()
        )
    builder.row(InlineKeyboardButton(text="🗂️ Архивные логи", callback_data="show_archived_logs"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    await callback.message.edit_text(
        "📝 <b>Экспорт логов</b>\n\nВыберите действие:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "show_archived_logs")
async def show_archived_logs_menu(callback: CallbackQuery):
    """Показывает меню с архивными логами (только даты)."""
    archived_logs = await get_archived_logs()
    builder = InlineKeyboardBuilder()
    if not archived_logs:
        await callback.answer("Архивных логов нет.", show_alert=True)
        return
    for filename in archived_logs:
        m = re.match(r"bot_(\d{4})-(\d{2})-(\d{2})\.log", filename)
        if m:
            date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            display_name = date_str
        else:
            display_name = filename
        builder.button(
            text=display_name,
            callback_data=LogCallback(filename=filename).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="get_logs"))

    await callback.message.edit_text(
        "�️ <b>Архивные логи</b>\n\nВыберите дату:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(LogCallback.filter())
async def send_log_file(callback: CallbackQuery, callback_data: LogCallback):
    """
    Отправляет выбранный файл логов администратору.
    """
    filename = callback_data.filename
    log_path = os.path.join(LOG_DIR, filename)
    user_id = callback.from_user.id

    if not await asyncio.to_thread(os.path.exists, log_path):
        logging.warning(f"Админ {user_id} запросил несуществующий лог: {filename}")
        await callback.answer(f"❗️ Файл <b>{filename}</b> не найден.", show_alert=True, parse_mode="HTML")
        return

    if await asyncio.to_thread(os.path.getsize, log_path) == 0:
        logging.info(f"Админ {user_id} запросил пустой лог: {filename}")
        await callback.answer(f"⚠️ Файл <b>{filename}</b> пуст.", show_alert=True, parse_mode="HTML")
        return

    logging.info(f"Админ {user_id} запросил лог: {filename}")

    file = FSInputFile(log_path)
    await callback.message.answer_document(file, caption=f"📄 Ваш лог: <code>{filename}</code>", parse_mode="HTML")
    await callback.answer()