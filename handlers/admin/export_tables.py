"""Экспорт таблиц: динамический CSV любой модели SQLAlchemy через инлайн-меню."""

import csv
import logging
from datetime import datetime
import aiofiles
import io

from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

import db
from db.base import Base, get_session

logger = logging.getLogger(__name__)
router = Router()

class TableExportCallback(CallbackData, prefix="export"):
    """Фабрика колбэков для экспорта таблиц."""
    table_name: str


def get_all_models():
    """
    Динамически получает все модели, унаследованные от Base.
    Работает благодаря тому, что все модели импортированы в db/__init__.py.
    """
    # Сортируем модели по имени таблицы для предсказуемого порядка кнопок
    return sorted(Base.registry.mappers, key=lambda m: m.class_.__tablename__)


def get_table_keyboard() -> InlineKeyboardBuilder:
    """
    Создает клавиатуру со списком всех доступных для экспорта таблиц с эмодзи и дружелюбными подписями.
    """
    builder = InlineKeyboardBuilder()
    models = get_all_models()

    for mapper in models:
        model_class = mapper.class_
        table_name = model_class.__tablename__
        builder.button(
            text=f"📄 {table_name}",
            callback_data=TableExportCallback(table_name=table_name).pack()
        )

    builder.button(text="⬅️ Назад в меню", callback_data="admin_menu")
    builder.adjust(2)
    return builder


@router.callback_query(F.data == "export_table_menu")
async def export_table_menu(callback: CallbackQuery) -> None:
    """
    Отображает меню выбора таблиц для экспорта с дружелюбным текстом и эмодзи.
    """
    builder = get_table_keyboard()
    await callback.message.edit_text(
        "<b>📄 Экспорт таблиц</b>\n\nВыберите таблицу для экспорта в формате CSV:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


def format_value(value):
    """Форматирует значения для корректной записи в CSV."""
    if isinstance(value, datetime):
        return value.astimezone().strftime('%Y-%m-%d %H:%M:%S')
    if value is None:
        return ""
    return str(value)


@router.callback_query(TableExportCallback.filter())
async def export_table_handler(callback: CallbackQuery, callback_data: TableExportCallback) -> None:
    """
    Универсальный обработчик экспорта любой таблицы в формат CSV с дружелюбным UX и эмодзи.
    """
    table_name = callback_data.table_name
    await callback.answer(f"⏳ Готовим экспорт таблицы <b>{table_name}</b>...", show_alert=False)

    try:
        model_mapper = next((m for m in get_all_models() if m.class_.__tablename__ == table_name), None)

        if not model_mapper:
            await callback.answer(f"❌ <b>Таблица '{table_name}' не найдена.</b>", show_alert=True)
            return

        model_class = model_mapper.class_

        async with get_session() as session:
            result = await session.execute(select(model_class))
            rows = result.scalars().all()

            if not rows:
                await callback.message.edit_text(
                    f"ℹ️ <b>Таблица <code>{table_name}</code> пуста.</b>\n\n"
                    "Выберите другую таблицу для экспорта:",
                    parse_mode="HTML",
                    reply_markup=callback.message.reply_markup
                )
                await callback.answer()
                return

            headers = [c.name for c in model_class.__table__.columns]

        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
        for row_obj in rows:
            writer.writerow([format_value(getattr(row_obj, h)) for h in headers])
        csv_text = csv_buffer.getvalue()
        csv_buffer.close()
        async with aiofiles.tempfile.NamedTemporaryFile('w+', encoding='utf-8', delete=False) as tmp:
            await tmp.write(csv_text)
            await tmp.flush()
            tmp_path = tmp.name

        async with aiofiles.open(tmp_path, 'rb') as f:
            csv_data = await f.read()

        if not csv_data or len(csv_data) == 0:
            await callback.answer(
                f"ℹ️ <b>Таблица <code>{table_name}</code> пуста или файл не создан.</b>",
                show_alert=True
            )
            await aiofiles.os.remove(tmp_path)
            return
        file = BufferedInputFile(csv_data, filename=f"{table_name}.csv")
        await callback.message.answer_document(
            file,
            caption=f"📄 <b>Экспорт таблицы:</b> <code>{table_name}.csv</code>",
            parse_mode="HTML"
        )
        logger.info(f"📤 [EXPORT] Таблица '{table_name}' экспортирована пользователю {callback.from_user.id}")
        await callback.answer("✅ Файл успешно отправлен!", show_alert=False)
        await aiofiles.os.remove(tmp_path)

    except Exception as e:
        logger.error(f"Ошибка при экспорте таблицы {table_name}: {e}", exc_info=True)
        await callback.answer(
            f"❌ <b>Произошла ошибка при экспорте таблицы <code>{table_name}</code>.</b>\nПроверьте логи.",
            show_alert=True
        )
