"""Управление промокодами в админ-панели: добавление, удаление, просмотр и массовое очищение."""

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup

from config import ADMINS
from db.base import get_session
from db.promocodes import (add_promocode, get_all_promocodes,
                           remove_all_promocodes, remove_promocode)
from states.promo import PromoStates

router = Router()


# --- Клавиатуры и навигация ---

def get_promo_menu_keyboard():
    """
    Возвращает клавиатуру для меню управления промокодами с эмодзи и дружелюбными подписями.
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить промокод", callback_data="add_promocode"))
    builder.row(InlineKeyboardButton(text="➖ Удалить промокод", callback_data="remove_promocode"))
    builder.row(InlineKeyboardButton(text="🎟️ Посмотреть все", callback_data="all_promocodes"))
    builder.row(InlineKeyboardButton(text="🗑️ Удалить все", callback_data="remove_all_promocodes"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_menu"))
    return builder.as_markup()


async def show_promo_menu(callback: CallbackQuery) -> None:
    """
    Отображает главное меню управления промокодами с дружелюбным приветствием.
    """
    await callback.message.edit_text(
        "<b>🎟️ Меню управления промокодами</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_promo_menu_keyboard()
    )
    await callback.answer()


# --- Добавление промокода ---
@router.callback_query(F.data == "add_promocode")
async def add_promocode_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Запускает процесс добавления нового промокода с дружелюбной инструкцией и эмодзи.
    """
    await callback.message.answer(
        "<b>➕ Добавление промокода</b>\n\n"
        "Пожалуйста, введите данные для нового промокода.\n\n"
        "<b>Формат:</b> <code>КОД ДНИ [КОЛ-ВО]</code>\n\n"
        "• <code>КОД</code> — сам промокод (без пробелов).\n"
        "• <code>ДНИ</code> — срок действия в днях.\n"
        "• <code>КОЛ-ВО</code> — необязательное число активаций (по умолчанию 1).\n\n"
        "<b>Пример 1 (одноразовый):</b> <code>SALE25 30</code>\n"
        "<b>Пример 2 (многоразовый):</b> <code>MULTI 90 100</code>\n\n"
        "Если передумаете — просто нажмите <b>Назад</b> в меню.",
        parse_mode="HTML"
    )
    await state.set_state(PromoStates.add)
    await callback.answer()


@router.message(PromoStates.add)
async def process_add_promocode(message: types.Message, state: FSMContext) -> None:
    """
    Обрабатывает введённые данные для нового промокода, отвечает дружелюбно и с эмодзи.
    """
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
            f"✅ <b>Промокод <code>{code.upper()}</code> на {days} дн. "
            f"({uses_left} активаций) успешно добавлен!</b>\n\n"
            "Спасибо за пополнение коллекции! 🎉",
            parse_mode="HTML"
        )
        await state.clear()
    else:
        logging.warning(f"Ошибка формата промокода от {message.from_user.id}: {message.text}")
        await message.answer(
            "❗️ <b>Неверный формат промокода.</b>\n\n"
            "Пожалуйста, попробуйте ещё раз по примеру выше или нажмите <b>Назад</b> в меню.",
            parse_mode="HTML"
        )


# --- Удаление одного промокода ---


# --- Новый способ: удаление промокода через кнопки ---
@router.callback_query(F.data == "remove_promocode")
async def remove_promocode_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Показывает список промокодов для удаления по кнопке, с эмодзи и дружелюбным текстом.
    """
    async with get_session() as session:
        promocodes = await get_all_promocodes(session)
    if not promocodes:
        await callback.message.edit_text(
            "❌ <b>Нет активных промокодов.</b>\n\nДобавьте новый промокод, чтобы начать!",
            parse_mode="HTML",
            reply_markup=get_promo_menu_keyboard()
        )
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for p in promocodes:
        builder.button(
            text=f"🎟️ {p.code} — {p.duration_days} дн. (ост: {p.uses_left})",
            callback_data=f"remove_promo:{p.code}"
        )
    builder.button(text="⬅️ Назад в меню", callback_data="promocode_menu_show")
    builder.adjust(1)
    await callback.message.edit_text(
        "<b>🗑️ Выберите промокод для удаления:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# --- Обработка нажатия на кнопку удаления конкретного промокода ---
@router.callback_query(F.data.startswith("remove_promo:"))
async def remove_promocode_button(callback: CallbackQuery) -> None:
    """
    Обрабатывает нажатие на кнопку удаления конкретного промокода, отвечает дружелюбно.
    """
    code = callback.data.removeprefix("remove_promo:")
    async with get_session() as session:
        success = await remove_promocode(session, code)
    if success:
        text = f"✅ <b>Промокод <code>{code.upper()}</code> успешно удалён!</b>"
    else:
        text = f"❗️ <b>Промокод <code>{code.upper()}</code> не найден.</b>"
    markup = callback.message.reply_markup
    if markup:
        new_buttons = [row for row in markup.inline_keyboard if not any(code in btn.callback_data for btn in row if btn.callback_data)]
        if len(new_buttons) == 1 and any("Назад" in btn.text for btn in new_buttons[0]):
            await callback.message.edit_text(
                "❌ <b>Нет активных промокодов.</b>\n\nДобавьте новый промокод, чтобы начать!",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_buttons))
    await callback.answer(text, show_alert=True)


@router.message(PromoStates.remove)
async def process_remove_promocode(message: types.Message, state: FSMContext) -> None:
    """
    Обрабатывает введённый для удаления промокод, отвечает дружелюбно и с эмодзи.
    """
    if message.from_user.id not in ADMINS or not message.text:
        await state.clear()
        return

    code = message.text.strip()
    async with get_session() as session:
        success = await remove_promocode(session, code)
        if success:
            logging.info(f"Админ {message.from_user.id} удалил промокод: {code}.")
            text = f"✅ <b>Промокод <code>{code.upper()}</code> успешно удалён!</b>"
        else:
            text = f"❗️ <b>Промокод <code>{code.upper()}</code> не найден.</b>"

    await message.answer(text, parse_mode="HTML")
    await state.clear()


# --- Просмотр всех промокодов ---

@router.callback_query(F.data == "all_promocodes")
async def show_all_promocodes(callback: CallbackQuery) -> None:
    """
    Показывает список всех активных промокодов с эмодзи и дружелюбным текстом.
    """
    async with get_session() as session:
        promocodes = await get_all_promocodes(session)

        if promocodes:
            text = "<b>🎟️ Активные промокоды:</b>\n\n" + "\n".join(
                [
                    f"🎟️ <code>{p.code}</code> — {p.duration_days} дн. (осталось: {p.uses_left})"
                    for p in promocodes
                ]
            )
        else:
            text = "❌ <b>Нет активных промокодов.</b>\n\nДобавьте новый промокод, чтобы начать!"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="promocode_menu_show"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# --- Удаление ВСЕХ промокодов (с подтверждением) ---

@router.callback_query(F.data == "remove_all_promocodes")
async def ask_remove_all_confirmation(callback: CallbackQuery) -> None:
    """
    Запрашивает подтверждение на удаление всех промокодов с акцентом на необратимость и эмодзи.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑️ Да, удалить все", callback_data="confirm_remove_all"),
        InlineKeyboardButton(text="🚫 Отмена", callback_data="promocode_menu_show")
    )
    await callback.message.edit_text(
        "<b>⚠️ Вы уверены, что хотите удалить <u>абсолютно все</u> промокоды?</b>\n\n"
        "Это действие <b>необратимо</b>. Пожалуйста, подтвердите свой выбор:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_remove_all")
async def confirm_remove_all_promocodes(callback: CallbackQuery) -> None:
    """
    Окончательно удаляет все промокоды, возвращает в меню и сообщает дружелюбно.
    """
    async with get_session() as session:
        await remove_all_promocodes(session)
        logging.warning(f"Админ {callback.from_user.id} удалил ВСЕ промокоды.")

    await callback.answer("✅ <b>Все промокоды были успешно удалены!</b>", show_alert=True)
    await show_promo_menu(callback)


# --- Возврат в меню ---

@router.callback_query(F.data == "promocode_menu_show")
async def back_to_promo_menu(callback: CallbackQuery) -> None:
    """
    Обрабатывает кнопку 'Назад', возвращая в меню промокодов.
    """
    await show_promo_menu(callback)