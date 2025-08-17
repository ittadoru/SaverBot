"""Управление промокодами в админ-панели: добавление, удаление, просмотр и массовое очищение."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

from config import ADMINS
from db.base import get_session
from db.promocodes import (add_promocode, get_all_promocodes,
                           remove_all_promocodes, remove_promocode)
from states.promo import PromoStates

router = Router()


# --- Клавиатуры и навигация ---

def get_promo_menu_keyboard():
    """Возвращает клавиатуру для меню управления промокодами."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить промокод", callback_data="add_promocode"))
    builder.row(InlineKeyboardButton(text="➖ Удалить промокод", callback_data="remove_promocode"))
    builder.row(InlineKeyboardButton(text="🎟 Все промокоды", callback_data="all_promocodes"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить все промокоды", callback_data="remove_all_promocodes"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))
    return builder.as_markup()


async def show_promo_menu(callback: CallbackQuery):
    """Отображает меню управления промокодами."""
    await callback.message.edit_text(
        "Меню промокодов:",
        reply_markup=get_promo_menu_keyboard()
    )
    await callback.answer()


# --- Добавление промокода ---
@router.callback_query(F.data == "add_promocode")
async def add_promocode_start(callback: CallbackQuery, state: FSMContext):
    """Запускает процесс добавления нового промокода."""
    await callback.message.answer(
        "Введите данные для промокода.\n\n"
        "<b>Формат:</b> <code>КОД ДНИ [КОЛ-ВО]</code>\n\n"
        "• <code>КОД</code> — сам промокод (без пробелов).\n"
        "• <code>ДНИ</code> — срок действия в днях.\n"
        "• <code>КОЛ-ВО</code> — необязательное число активаций (по умолч. 1).\n\n"
        "<b>Пример 1 (одноразовый):</b> <code>SALE25 30</code>\n"
        "<b>Пример 2 (многоразовый):</b> <code>MULTI 90 100</code>",
        parse_mode="HTML"
    )
    await state.set_state(PromoStates.add)
    await callback.answer()


@router.message(PromoStates.add)
async def process_add_promocode(message: types.Message, state: FSMContext):
    """Обрабатывает введенные данные для нового промокода."""
    if message.from_user.id not in ADMINS or not message.text:
        await state.clear()
        return

    parts = message.text.strip().split()
    code, days, uses_left = None, None, 1

    if len(parts) == 2 and parts[1].isdigit():
        code, days = parts[0], int(parts[1])
    elif len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        code, days, uses_left = parts[0], int(parts[1]), int(parts[2])

    if code and days:
        async with get_session() as session:
            await add_promocode(session, code, days, uses_left)

        logging.info(
            f"Админ {message.from_user.id} добавил промокод: {code}, "
            f"{days} дн., {uses_left} исп."
        )
        await message.answer(
            f"✅ Промокод <code>{code.upper()}</code> на {days} дн. "
            f"({uses_left} активаций) успешно добавлен."
        )
        await state.clear()
    else:
        await message.answer(
            "❗️ <b>Неверный формат.</b> Попробуйте еще раз.\n"
            "Формат: <code>КОД ДНИ [КОЛИЧЕСТВО]</code>",
            parse_mode="HTML"
        )


# --- Удаление одного промокода ---

@router.callback_query(F.data == "remove_promocode")
async def remove_promocode_start(callback: CallbackQuery, state: FSMContext):
    """Запускает процесс удаления промокода."""
    await callback.message.answer("Введите промокод, который хотите удалить:")
    await state.set_state(PromoStates.remove)
    await callback.answer()


@router.message(PromoStates.remove)
async def process_remove_promocode(message: types.Message, state: FSMContext):
    """Обрабатывает введенный для удаления промокод."""
    if message.from_user.id not in ADMINS or not message.text:
        await state.clear()
        return

    code = message.text.strip()
    async with get_session() as session:
        success = await remove_promocode(session, code)
        if success:
            logging.info(f"Админ {message.from_user.id} удалил промокод: {code}.")
            text = f"✅ Промокод <code>{code.upper()}</code> удалён."
        else:
            text = f"❗️ Промокод <code>{code.upper()}</code> не найден."

    await message.answer(text, parse_mode="HTML")
    await state.clear()


# --- Просмотр всех промокодов ---

@router.callback_query(F.data == "all_promocodes")
async def show_all_promocodes(callback: CallbackQuery):
    """Показывает список всех активных промокодов."""
    async with get_session() as session:
        promocodes = await get_all_promocodes(session)

        if promocodes:
            text = "<b>🎟 Активные промокоды:</b>\n\n" + "\n".join(
                [
                    f"<code>{p.code}</code> — {p.duration_days} дн. "
                    f"(осталось: {p.uses_left})"
                    for p in promocodes
                ]
            )
        else:
            text = "❌ Нет активных промокодов."

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="promocode_menu_show"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# --- Удаление ВСЕХ промокодов (с подтверждением) ---

@router.callback_query(F.data == "remove_all_promocodes")
async def ask_remove_all_confirmation(callback: CallbackQuery):
    """Запрашивает подтверждение на удаление всех промокодов."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Да, удалить все", callback_data="confirm_remove_all"),
        InlineKeyboardButton(text="🚫 Отмена", callback_data="promocode_menu_show")
    )
    await callback.message.edit_text(
        "<b>Вы уверены, что хотите удалить абсолютно все промокоды?</b>\n"
        "Это действие необратимо.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_remove_all")
async def confirm_remove_all_promocodes(callback: CallbackQuery):
    """Окончательно удаляет все промокоды и возвращает в меню."""
    async with get_session() as session:
        await remove_all_promocodes(session)
        logging.warning(f"Админ {callback.from_user.id} удалил ВСЕ промокоды.")

    await callback.answer("✅ Все промокоды были успешно удалены.", show_alert=True)
    await show_promo_menu(callback)


# --- Возврат в меню ---

@router.callback_query(F.data == "promocode_menu_show")
async def back_to_promo_menu(callback: CallbackQuery):
    """Обрабатывает кнопку 'Назад', возвращая в меню промокодов."""
    await show_promo_menu(callback)