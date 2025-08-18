"""Экспорт логов: список доступных файлов и отправка выбранного админу."""

import logging
import os
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


def get_log_files():
    """
    Сканирует директорию логов и возвращает отсортированный список файлов.
    Текущий лог 'bot.log' всегда первый, за ним идут архивные.
    """
    if not os.path.exists(LOG_DIR):
        return []

    files = os.listdir(LOG_DIR)

    # Паттерн для архивных логов, создаваемых TimedRotatingFileHandler
    # Например, 'bot.log.2023-10-27'
    log_pattern = re.compile(r"^bot\.log\.(\d{4}-\d{2}-\d{2})$")

    current_log = "bot.log"
    archived_logs = sorted(
        [f for f in files if log_pattern.match(f)],
        reverse=True
    )

    # Формируем итоговый список
    log_files = []
    if current_log in files:
        log_files.append(current_log)

    log_files.extend(archived_logs)

    return log_files


@router.callback_query(F.data == "get_logs")
async def show_log_menu(callback: CallbackQuery):
    """
    Показывает меню со всеми доступными файлами логов в виде единого списка.
    """
    log_files = get_log_files()

    if not log_files:
        await callback.answer("🗂️ Логи не найдены.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()

    for filename in log_files:
        # Для 'bot.log' показываем "Текущий", для остальных - дату
        if filename == "bot.log":
            display_name = "📄 Текущий лог"
        else:
            date_str = filename.replace("bot.log.", "")
            display_name = f"🗂️ Архив {date_str}"

        builder.button(
            text=display_name,
            callback_data=LogCallback(filename=filename).pack()
        )

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    await callback.message.edit_text(
        "📝 <b>Экспорт логов</b>\n\nВыберите нужный файл:",
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

    if not os.path.exists(log_path):
        logging.warning(f"Админ {user_id} запросил несуществующий лог: {filename}")
        await callback.answer(f"❗️ Файл <b>{filename}</b> не найден.", show_alert=True, parse_mode="HTML")
        return

    if os.path.getsize(log_path) == 0:
        logging.info(f"Админ {user_id} запросил пустой лог: {filename}")
        await callback.answer(f"⚠️ Файл <b>{filename}</b> пуст.", show_alert=True, parse_mode="HTML")
        return

    logging.info(f"Админ {user_id} запросил лог: {filename}")

    file = FSInputFile(log_path)
    await callback.message.answer_document(file, caption=f"📄 Ваш лог: <code>{filename}</code>", parse_mode="HTML")
    await callback.answer()
