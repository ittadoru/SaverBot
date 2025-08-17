"""Общий конструктор рассылок (текст + опциональная кнопка) для трёх типов.

Убирает дублирование между:
- Общей рассылкой (всем)
- Рекламной (без активной подписки)
- Неплатившие (has_paid_ever = false)

Использование:
    from utils.broadcast_base import register_broadcast_constructor
    router = Router()
    async def audience_fetcher(): ...  # -> list[int]
    register_broadcast_constructor(
        router,
        start_trigger="broadcast_start",
        prefix="broadcast",
        title="📢 **Конструктор общей рассылки**",
        send_button_label="🚀 Отправить",
        start_status_text="⏳ Рассылка всем пользователям начинается...",
        summary_title="✅ **Общая рассылка завершена!**",
        total_label="Всего пользователей для рассылки",
        audience_fetcher=audience_fetcher,
    )
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Awaitable, Callable

from aiogram import F, Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

class BroadcastStates(StatesGroup):
    """Единые состояния ввода для всех типов рассылок."""
    waiting_text = State()
    waiting_button_text = State()
    waiting_button_url = State()

AudienceFetcher = Callable[[], Awaitable[list[int]]]

def _keyboard(prefix: str, send_button_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Текст", callback_data=f"{prefix}:set_text"),
                InlineKeyboardButton(text="🔗 Кнопка", callback_data=f"{prefix}:set_button"),
            ],
            [InlineKeyboardButton(text="👀 Предпросмотр", callback_data=f"{prefix}:preview")],
            [
                InlineKeyboardButton(text=send_button_label, callback_data=f"{prefix}:send"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}:cancel"),
            ],
        ]
    )

async def _edit_constructor(message: Message, state: FSMContext, title: str, prefix: str, send_button_label: str) -> None:
    with suppress(TelegramAPIError):
        await message.edit_text(title, reply_markup=_keyboard(prefix, send_button_label), parse_mode="Markdown")

def register_broadcast_constructor(
    router: Router,
    *,
    start_trigger: str,
    prefix: str,
    title: str,
    send_button_label: str,
    start_status_text: str,
    summary_title: str,
    total_label: str,
    audience_fetcher: AudienceFetcher,
    per_message_delay: float = 0.1,
) -> None:
    """Регистрирует полный набор хендлеров конструктора + отправки.

    Формат callback_data: ``{prefix}:{action}``.
    """

    @router.callback_query(F.data == start_trigger)
    async def _start(callback: CallbackQuery, state: FSMContext) -> None:  # noqa: D401
        await state.clear()
        await state.update_data(constructor_message_id=callback.message.message_id)
        await _edit_constructor(callback.message, state, title, prefix, send_button_label)
        await callback.answer()

    @router.callback_query(F.data == f"{prefix}:cancel")
    async def _cancel(callback: CallbackQuery, state: FSMContext) -> None:
        from handlers.admin.menu import get_admin_menu_keyboard  # локальный импорт
        await state.clear()
        await callback.message.edit_text("🔐 Админ-панель", reply_markup=get_admin_menu_keyboard())
        await callback.answer()

    @router.callback_query(F.data == f"{prefix}:set_text")
    async def _set_text(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(BroadcastStates.waiting_text)
        prompt = await callback.message.answer("Введите текст рассылки:")
        await state.update_data(prompt_message_id=prompt.message_id)
        await callback.answer()

    @router.message(BroadcastStates.waiting_text)
    async def _process_text(message: Message, state: FSMContext, bot: Bot) -> None:
        await state.update_data(text=message.text)
        await state.set_state(None)
        data = await state.get_data()
        constructor_msg_id = data.get("constructor_message_id")
        prompt_msg_id = data.get("prompt_message_id")
        with suppress(TelegramAPIError):
            if prompt_msg_id:
                await bot.delete_message(message.chat.id, prompt_msg_id)
            await message.delete()
        if constructor_msg_id:
            constructor_message = Message(message_id=constructor_msg_id, chat=message.chat, bot=bot)
            await _edit_constructor(constructor_message, state, title, prefix, send_button_label)

    @router.callback_query(F.data == f"{prefix}:set_button")
    async def _set_button_text(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(BroadcastStates.waiting_button_text)
        prompt = await callback.message.answer("Введите текст кнопки:")
        await state.update_data(prompt_message_id=prompt.message_id)
        await callback.answer()

    @router.message(BroadcastStates.waiting_button_text)
    async def _process_button_text(message: Message, state: FSMContext, bot: Bot) -> None:
        await state.update_data(button_text=message.text)
        await state.set_state(BroadcastStates.waiting_button_url)
        data = await state.get_data()
        prompt_msg_id = data.get("prompt_message_id")
        with suppress(TelegramAPIError):
            if prompt_msg_id:
                await bot.delete_message(message.chat.id, prompt_msg_id)
            await message.delete()
        prompt = await message.answer("Теперь введите URL (http/https):")
        await state.update_data(prompt_message_id=prompt.message_id)

    @router.message(BroadcastStates.waiting_button_url)
    async def _process_button_url(message: Message, state: FSMContext, bot: Bot) -> None:
        url = (message.text or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            await message.answer("Неверный URL. Начните с http:// или https://")
            return
        await state.update_data(button_url=url)
        await state.set_state(None)
        data = await state.get_data()
        constructor_msg_id = data.get("constructor_message_id")
        prompt_msg_id = data.get("prompt_message_id")
        with suppress(TelegramAPIError):
            if prompt_msg_id:
                await bot.delete_message(message.chat.id, prompt_msg_id)
            await message.delete()
        if constructor_msg_id:
            constructor_message = Message(message_id=constructor_msg_id, chat=message.chat, bot=bot)
            await _edit_constructor(constructor_message, state, title, prefix, send_button_label)

    @router.callback_query(F.data == f"{prefix}:preview")
    async def _preview(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        text = data.get("text")
        if not text:
            await callback.answer("❗️ Сначала задайте текст.", show_alert=True)
            return
        button_text = data.get("button_text")
        button_url = data.get("button_url")
        markup = None
        if button_text and button_url:
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=button_text, url=button_url)]])
        await callback.message.answer(text, reply_markup=markup)
        await callback.answer()

    @router.callback_query(F.data == f"{prefix}:send")
    async def _send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
        data = await state.get_data()
        text = data.get("text")
        if not text:
            await callback.answer("❗️ Пустое сообщение.", show_alert=True)
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]])
        await callback.message.edit_text(start_status_text, reply_markup=keyboard)
        asyncio.create_task(_send_task(bot, callback.from_user.id, data))
        await state.clear()
        await callback.answer()

    async def _send_task(bot: Bot, admin_id: int, data: dict) -> None:
        text = data.get("text")
        button_text = data.get("button_text")
        button_url = data.get("button_url")
        markup = None
        if button_text and button_url:
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=button_text, url=button_url)]])
        sent = 0
        failed = 0
        user_ids = await audience_fetcher()
        total = len(user_ids)
        logger.info(f"Начинается рассылка '{prefix}' для {total} пользователей.")
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, text, reply_markup=markup)
                sent += 1
            except TelegramAPIError as e:  # noqa: PERF203 - допустимо логировать
                logger.warning("Не удалось отправить сообщение пользователю %s: %s", user_id, e)
                failed += 1
            await asyncio.sleep(per_message_delay)
        logger.info("Рассылка '%s' завершена. Отправлено=%s Ошибок=%s", prefix, sent, failed)
        summary_text = (
            f"{summary_title}\n\n"
            f"👥 {total_label}: {total}\n"
            f"👍 Успешно отправлено: {sent}\n"
            f"👎 Не удалось доставить: {failed}"
        )
        with suppress(TelegramAPIError):
            await bot.send_message(admin_id, summary_text, parse_mode="Markdown")
