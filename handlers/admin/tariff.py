from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from states.tariff import TariffStates
from utils.redis import create_tariff, delete_tariff, get_all_tariffs
from config import ADMINS
import logging

router = Router()

@router.callback_query(F.data == "tariff_menu")
async def tariff_menu(callback: CallbackQuery):
    """Показывает меню управления тарифами для администратора."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить тариф", callback_data="add_tariff")],
        [InlineKeyboardButton(text="➖ Удалить тариф", callback_data="remove_tariff")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
    ])
    await callback.message.edit_text("Меню тарифов:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "add_tariff")
async def start_add_tariff(callback: CallbackQuery, state: FSMContext):
    """Запрашивает у администратора название нового тарифа."""
    await callback.message.answer("Введите название тарифа:")
    await state.set_state(TariffStates.waiting_for_name)
    await callback.answer()

@router.callback_query(F.data == "remove_tariff")
async def show_tariffs_for_removal(callback: CallbackQuery):
    """Показывает список тарифов для удаления."""
    tariffs = await get_all_tariffs()
    if not tariffs:
        await callback.message.edit_text("Список тарифов пуст.")
        await callback.answer()
        return
    # Формируем клавиатуру с тарифами для удаления
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{t.name} ({t.duration_days} дней, {t.price} ₽) ❌",
            callback_data=f"delete_tariff:{t.id}"
        )] for t in tariffs
    ])
    await callback.message.edit_text("Выберите тариф для удаления:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("delete_tariff:"))
async def delete_tariff_handler(callback: CallbackQuery):
    """Удаляет выбранный тариф и обновляет список."""
    tariff_id = int(callback.data.split(":")[1])
    await delete_tariff(tariff_id)
    logging.info(f"Admin {callback.from_user.id} deleted tariff {tariff_id}")
    await callback.answer("Тариф удалён.")
    # Обновляем список тарифов после удаления
    await show_tariffs_for_removal(callback)

@router.message(TariffStates.waiting_for_name)
async def process_tariff_name(message: Message, state: FSMContext):
    """Сохраняет название тарифа и запрашивает длительность."""
    await state.update_data(name=message.text.strip())
    await message.answer("Введите длительность тарифа в днях:")
    await state.set_state(TariffStates.waiting_for_days)

@router.message(TariffStates.waiting_for_days)
async def process_tariff_days(message: Message, state: FSMContext):
    """Сохраняет длительность тарифа и запрашивает цену."""
    if not message.text.isdigit():
        return await message.answer("Введите число дней:")
    await state.update_data(days=int(message.text.strip()))
    await message.answer("Введите цену тарифа в рублях:")
    await state.set_state(TariffStates.waiting_for_price)

@router.message(TariffStates.waiting_for_price)
async def process_tariff_price(message: Message, state: FSMContext):
    """Создаёт тариф с указанными параметрами."""
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        return await message.answer("Введите цену числом (например, 99.0):")

    data = await state.get_data()
    name = data["name"]
    days = data["days"]

    # Создаём тариф в Redis
    await create_tariff(name=name, price=price, duration_days=days)
    logging.info(f"Admin {message.from_user.id} created tariff '{name}' ({days} days, {price} RUB)")

    await message.answer(f"✅ Тариф «{name}» добавлен: {days} дней, {price} RUB.")
    await state.clear()
