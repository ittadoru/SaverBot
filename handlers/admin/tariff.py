"""Админ: управление тарифами (список, добавление, редактирование, удаление)."""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMINS
from db.base import get_session
from db.tariff import create_tariff, delete_tariff, get_all_tariffs, update_tariff
from states.tariff import TariffStates

# Инициализация логгера для этого модуля
logger = logging.getLogger(__name__)

# Создание роутера и применение фильтра ко всем хендлерам (только для админов)
router = Router()
router.message.filter(F.from_user.id.in_(ADMINS))
router.callback_query.filter(F.from_user.id.in_(ADMINS))


@router.callback_query(F.data == "tariff_menu")
async def tariff_menu_callback(callback: CallbackQuery) -> None:
    """Обрабатывает нажатие на кнопку 'tariff_menu'."""
    await tariff_menu(message=callback.message, edit=True)
    await callback.answer()


async def tariff_menu(message: Message, edit: bool = False) -> None:
    """Отображает меню управления тарифами + сводку по существующим тарифам."""
    async with get_session() as session:
        tariffs = await get_all_tariffs(session)
    summary_lines = ["Меню управления тарифами:"]
    if tariffs:
        for t in tariffs:
            summary_lines.append(f"• #{t.id} {t.name} — {t.duration_days} дн / {t.price} ₽")
    else:
        summary_lines.append("(пока нет тарифов)")
    text = "\n".join(summary_lines)
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить", callback_data="add_tariff")
    if tariffs:
        builder.button(text="✏ Изменить", callback_data="edit_tariff_pick")
        builder.button(text="✖ Удалить", callback_data="delete_tariff_menu")
    builder.button(text="⬅️ Назад", callback_data="admin_menu")
    builder.adjust(1)
    if edit:
        await message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "delete_tariff_menu")
async def delete_tariff_menu_callback(callback: CallbackQuery) -> None:
    """Отображает меню для удаления тарифов."""
    async with get_session() as session:
        tariffs = await get_all_tariffs(session)

    builder = InlineKeyboardBuilder()
    if not tariffs:
        builder.button(text="⬅️ Назад", callback_data="tariff_menu")
        await callback.message.edit_text(
            "Список тарифов пуст.", reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    for t in tariffs:
        builder.button(
            text=f"❌ {t.name} ({t.duration_days} д., {t.price} ₽)",
            callback_data=f"delete_tariff_confirm:{t.id}",
        )
    builder.button(text="⬅️ Назад", callback_data="tariff_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "Выберите тариф для удаления:", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_tariff")
async def start_add_tariff(callback: CallbackQuery, state: FSMContext) -> None:
    """Начинает процесс добавления нового тарифа."""
    await callback.message.edit_text("Введите название нового тарифа (или /cancel):")
    await state.set_state(TariffStates.waiting_for_name)
    await callback.answer()


@router.callback_query(F.data.startswith("delete_tariff_confirm:"))
async def delete_tariff_handler(callback: CallbackQuery) -> None:
    """Удаляет выбранный тариф и обновляет меню удаления."""
    tariff_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        await delete_tariff(session, tariff_id)

    logger.info(
        "Администратор %d удалил тариф с id %d", callback.from_user.id, tariff_id
    )
    # Просто подтверждаем колбэк, чтобы убрать "часики"
    await callback.answer()

    # Обновляем меню удаления, чтобы показать актуальный список
    await delete_tariff_menu_callback(callback)


@router.message(TariffStates.waiting_for_name)
async def process_tariff_name(message: Message, state: FSMContext) -> None:
    """Обрабатывает название тарифа и запрашивает длительность."""
    if not message.text or len(message.text) > 50:
        await message.answer(
            "Название не должно быть пустым или длиннее 50 символов. "
            "Пожалуйста, введите корректное название:"
        )
        return
    await state.update_data(name=message.text.strip())
    await message.answer("Отлично! Теперь введите длительность тарифа в днях (целое число):")
    await state.set_state(TariffStates.waiting_for_days)


@router.message(TariffStates.waiting_for_days)
async def process_tariff_days(message: Message, state: FSMContext) -> None:
    """Обрабатывает длительность тарифа и запрашивает цену."""
    if not message.text.isdigit() or not 0 < int(message.text) < 10000:
        await message.answer(
            "Пожалуйста, введите корректное количество дней (целое число от 1 до 9999):"
        )
        return
    await state.update_data(days=int(message.text))
    await message.answer("Теперь введите цену тарифа в рублях (целое число, без копеек, например 199):")
    await state.set_state(TariffStates.waiting_for_price)


@router.message(TariffStates.waiting_for_price)
async def process_tariff_price(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод цены и создаёт новый тариф."""
    if not (message.text and message.text.isdigit() and 0 < int(message.text) < 1_000_000):
        await message.answer("Введите корректную ЦЕЛУЮ цену в рублях (1 .. 999999):")
        return
    price = int(message.text)

    data = await state.get_data()
    name = data["name"]
    days = data["days"]

    async with get_session() as session:
        await create_tariff(session, name=name, price=price, duration_days=days)

    logger.info(
        "Админ %d создал новый тариф: %s, %d дней, %d RUB",
        message.from_user.id,
        name,
        days,
        price,
    )

    await message.answer(
        f"✅ Тариф «{name}» успешно добавлен!\n"
        f"Длительность: {days} дней\n"
        f"Цена: {price} ₽"
    )
    await state.clear()

    # Отображаем главное меню тарифов
    await tariff_menu(message=message)


# ---------------- Редактирование тарифов ----------------
@router.callback_query(F.data == "edit_tariff_pick")
async def edit_tariff_pick(callback: CallbackQuery, state: FSMContext) -> None:
    async with get_session() as session:
        tariffs = await get_all_tariffs(session)
    if not tariffs:
        await callback.answer("Нет тарифов", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    for t in tariffs:
        kb.button(text=f"#{t.id} {t.name}", callback_data=f"edit_tariff:{t.id}")
    kb.button(text="⬅ Назад", callback_data="tariff_menu")
    kb.adjust(1)
    await callback.message.edit_text("Выберите тариф для редактирования:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_tariff:"))
async def edit_tariff_field_select(callback: CallbackQuery, state: FSMContext) -> None:
    tariff_id = int(callback.data.split(":", 1)[1])
    await state.update_data(edit_tariff_id=tariff_id)
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Имя", callback_data="edit_field:name")
    kb.button(text="⏱ Дни", callback_data="edit_field:days")
    kb.button(text="💰 Цена", callback_data="edit_field:price")
    kb.button(text="⬅ Назад", callback_data="tariff_menu")
    kb.adjust(2, 2, 1)
    await callback.message.edit_text(f"Что изменить в тарифе #{tariff_id}?", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def edit_tariff_start(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    await state.update_data(edit_field=field)
    prompt_map = {
        "name": "Введите новое имя тарифа:",
        "days": "Введите новую длительность (целое число дней):",
        "price": "Введите новую цену (целое число руб.):",
    }
    await state.set_state(TariffStates.editing_new_value)
    await callback.message.edit_text(prompt_map[field])
    await callback.answer()


@router.message(TariffStates.editing_new_value)
async def process_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    tariff_id = data.get("edit_tariff_id")
    field = data.get("edit_field")
    if not tariff_id or not field:
        await message.answer("Состояние потеряно. Вернитесь в меню тарифов: /admin")
        await state.clear()
        return
    raw = (message.text or "").strip()
    update_kwargs = {}
    if field == "name":
        if not raw or len(raw) > 50:
            await message.answer("Некорректное имя (1..50 символов). Повторите:")
            return
        update_kwargs["name"] = raw
    elif field == "days":
        if not raw.isdigit() or not (0 < int(raw) < 10000):
            await message.answer("Некорректное число дней. Повторите:")
            return
        update_kwargs["duration_days"] = int(raw)
    elif field == "price":
        if not raw.isdigit() or not (0 < int(raw) < 1_000_000):
            await message.answer("Некорректная цена. Повторите:")
            return
        update_kwargs["price"] = int(raw)
    else:
        await message.answer("Неизвестное поле.")
        await state.clear()
        return
    async with get_session() as session:
        tariff = await update_tariff(session, tariff_id, **update_kwargs)
    if not tariff:
        await message.answer("Тариф не найден.")
    else:
        await message.answer("✅ Изменено.")
    await state.clear()
    await tariff_menu(message)
