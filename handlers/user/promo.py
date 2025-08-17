"""Активация промокодов: ввод, валидация, активация, повторные попытки и отмена."""

from __future__ import annotations

import logging
import re
from typing import Any

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from db.base import get_session
from db.promocodes import activate_promocode
from db.subscribers import get_subscriber_expiry
from states.promo import PromoStates

logger = logging.getLogger(__name__)

router = Router()

# Настройки валидации
MAX_CODE_LENGTH = 32
CODE_REGEX = re.compile(r"^[A-Z0-9_-]+$")


def _prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="promo_cancel")]]
    )


def _build_success_message(days: int, expiry_str: str | None) -> str:
    tail = f"\nНовая дата окончания: <b>{expiry_str}</b>" if expiry_str else ""
    return (
        "🎉 <b>Промокод успешно активирован!</b>\n"
        f"Ваша подписка продлена на <b>{days}</b> дн.{tail}"
    )


def _build_fail_message() -> str:
    return (
        "⚠️ <b>Промокод не найден или уже использован.</b>\n"
        "Попробуйте снова или нажмите Отмена."
    )


def _build_invalid_format_message() -> str:
    return (
        "❌ Неверный формат кода. Используйте только буквы/цифры/-, до 32 символов."
    )


def _build_same_code_message() -> str:
    return "ℹ️ Этот код уже проверяли. Введите другой или Отмена."


async def _safe_delete(bot: Any, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        pass
    except Exception:  # noqa: BLE001
        logger.debug("Не удалось удалить сообщение %s", message_id, exc_info=True)


@router.callback_query(F.data == "promo")
async def promo_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    await _show_promo_prompt(callback.message, state)
    await callback.answer()
    logger.debug("Старт ввода промокода user_id=%d", callback.from_user.id)

@router.message(F.text == "/promocode")
async def promo_command(message: types.Message, state: FSMContext) -> None:
    await _show_promo_prompt(message, state)

# --- Универсальный запуск промокода (и с кнопки, и с команды) ---
async def _show_promo_prompt(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state == PromoStates.user:
        await message.answer("Уже жду промокод…")
        return
    prompt = await message.answer(
        "🎟 Пожалуйста, введите промокод для активации:", reply_markup=_prompt_keyboard()
    )
    await state.update_data(last_bot_message_id=prompt.message_id, last_code=None)
    await state.set_state(PromoStates.user)

@router.callback_query(F.data == "promo_cancel")
async def promo_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Отмена процесса ввода промокода."""
    data = await state.get_data()
    await state.clear()
    # Пытаемся удалить приглашение
    last_id = data.get("last_bot_message_id")
    if last_id:
        await _safe_delete(callback.bot, callback.message.chat.id, last_id)
    await callback.answer("Отменено")
    logger.info("Отмена ввода промокода user_id=%d", callback.from_user.id)


@router.message(PromoStates.user)
async def process_user_promocode(message: types.Message, state: FSMContext) -> None:
    """Обрабатывает введённый промокод: валидация, активация, ответ.

    Логика:
      1. Нормализуем код.
      2. Проверяем формат / повтор.
      3. Пытаемся активировать.
      4. Редактируем приглашение (если есть); иначе отправляем новое.
      5. При успехе завершаем состояние, при неудаче ждём новый ввод.
    """
    if not message.text:
        await message.answer("Введите текстовый промокод или нажмите Отмена.")
        return

    raw = message.text
    # Нормализация: убираем пробелы внутри и вокруг
    code = re.sub(r"\s+", "", raw).upper()

    data = await state.get_data()
    last_code = data.get("last_code")
    last_bot_message_id = data.get("last_bot_message_id")

    # Валидация формата
    if not code or len(code) > MAX_CODE_LENGTH or not CODE_REGEX.match(code):
        text = _build_invalid_format_message()
        await _respond_update(message, last_bot_message_id, text, state=state)
        return

    # Повторный ввод того же кода
    if last_code and code == last_code:
        text = _build_same_code_message()
        await _respond_update(message, last_bot_message_id, text, state=state)
        return

    user = message.from_user
    # Пытаемся удалить сообщение пользователя с кодом (приватность / чистота)
    await _safe_delete(message.bot, message.chat.id, message.message_id)

    async with get_session() as session:
        duration: int | None = await activate_promocode(session, user.id, code)
        expiry_date = None
        if duration:
            expiry = await get_subscriber_expiry(session, user.id)
            if expiry:
                expiry_date = expiry.strftime('%d.%m.%Y %H:%M')

    if duration:
        text = _build_success_message(duration, expiry_date)
        success = True
    else:
        text = _build_fail_message()
        success = False

    logger.info(
        "promo_attempt user_id=%d code=%s success=%s duration=%s",  # краткий лог
        user.id,
        code,
        success,
        duration,
    )

    await _respond_update(message, last_bot_message_id, text, success, state)

    if success:
        await state.clear()
    else:
        # Запоминаем код, чтобы не проверять повтор
        await state.update_data(last_code=code)


async def _respond_update(
    message: types.Message,
    bot_msg_id: int | None,
    text: str,
    success: bool | None = None,
    state: FSMContext | None = None,
) -> None:
    """Редактирует старое приглашение или отправляет новое при необходимости.

    Особенности:
      - Подавляет 'message is not modified' чтобы не дублировать.
      - При fallback создаёт новое сообщение и запоминает его id.
      - success=True удаляет клавиатуру.
    """
    if bot_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=bot_msg_id,
                text=text,
                reply_markup=None if success else _prompt_keyboard(),
                parse_mode="HTML",
            )
            return
        except TelegramBadRequest as e:
            low = str(e).lower()
            if "message is not modified" in low:
                logger.debug("Промо: текст не изменился, пропускаем update (chat=%d)", message.chat.id)
                return
            if "message to edit not found" not in low:
                logger.debug("edit_message_text fallback: %s", e)
    sent = await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=None if success else _prompt_keyboard(),
    )
    if not success and state is not None:
        await state.update_data(last_bot_message_id=sent.message_id)
