import os
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from utils import logger as log
from states.log_export import LogExport

router = Router()


@router.callback_query(F.data == "last_logs")
async def send_last_logs(callback: CallbackQuery):
    """Отправка текущего файла логов (bot.log)."""
    log_path = "logs/bot.log"
    if os.path.exists(log_path):
        file = FSInputFile(log_path)
        log.log_message("Админ запросил последние логи", emoji="📄")
        await callback.message.answer_document(file, caption="📄 Логи за последнее время")
    else:
        await callback.message.answer("Файл логов не найден.")
    await callback.answer()


@router.callback_query(F.data == "custom_logs")
async def ask_date(callback: CallbackQuery, state: FSMContext):
    """Запрос даты для выгрузки логов по дате."""
    await callback.message.answer(
        "Введите дату логов в формате `ГГГГ-ММ-ДД`, например: `2025-08-01`"
    )
    await state.set_state(LogExport.waiting_for_date)
    await callback.answer()


@router.message(LogExport.waiting_for_date)
async def send_logs_by_date(message: Message, state: FSMContext):
    """Отправка логов за указанную пользователем дату."""
    user_date = message.text.strip()
    filename = f"logs/bot_{user_date}.log"

    if os.path.exists(filename):
        file = FSInputFile(filename)
        log.log_message(f"Админ запросил логи за {user_date}", emoji="📄")
        await message.answer_document(file, caption=f"📄 Логи за {user_date}")
    else:
        log.log_error(f"Файл логов за {user_date} не найден")
        await message.answer(f"Файл логов за {user_date} дату не найден.")

    await state.clear()
