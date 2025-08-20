"""Универсальный конструктор рассылок с поддержкой текста, кнопки и медиа для админки."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Awaitable, Callable
from handlers.user.referral import get_referral_stats
from db.base import get_session
from utils.keyboards import back_button
from config import BROADCAST_PROGRESS_UPDATE_INTERVAL, BROADCAST_PER_MESSAGE_DELAY

from aiogram import F, Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
import time


logger = logging.getLogger(__name__)

class BroadcastStates(StatesGroup):
    waiting_text = State()
    waiting_button_text = State()
    waiting_button_url = State()
    waiting_media = State()

AudienceFetcher = Callable[[], Awaitable[list[int]]]

def _keyboard(prefix: str, send_button_label: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📝 Текст", callback_data=f"{prefix}:set_text"),
         InlineKeyboardButton(text="🔗 Кнопка", callback_data=f"{prefix}:set_button"),
         InlineKeyboardButton(text="📎 Медиа", callback_data=f"{prefix}:set_media")],
        [InlineKeyboardButton(text="👀 Предпросмотр", callback_data=f"{prefix}:preview")],
        [InlineKeyboardButton(text=send_button_label, callback_data=f"{prefix}:send"),
         InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}:cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def _edit_constructor(message: Message, state: FSMContext, title: str, prefix: str, send_button_label: str, bot: Bot) -> None:
    with suppress(TelegramAPIError):
        await bot(message.edit_text(title, reply_markup=_keyboard(prefix, send_button_label), parse_mode="Markdown"))

def _render_progress_bar(sent, total, bar_length=10):
    percent = sent / total if total else 0
    filled = int(bar_length * percent)
    bar = '🟩' * filled + '⬜' * (bar_length - filled)
    return f"Прогресс: [{bar}] {int(percent*100)}% ({sent}/{total})"

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
) -> None:
    """Регистрирует полный набор хендлеров конструктора + отправки.

    Формат callback_data: ``{prefix}:{action}``.
    """

    @router.callback_query(F.data == start_trigger)
    async def _start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
        await state.clear()
        await state.update_data(constructor_message_id=callback.message.message_id)
        await _edit_constructor(callback.message, state, title, prefix, send_button_label, bot)
        await callback.answer()

    @router.callback_query(F.data == f"{prefix}:cancel")
    async def _cancel(callback: CallbackQuery, state: FSMContext) -> None:
        from handlers.admin.menu import get_admin_menu_keyboard
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
        await _cleanup(message, state, bot, title, prefix, send_button_label)

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
        await _cleanup(message, state, bot)
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
        await _cleanup(message, state, bot, title, prefix, send_button_label)

    @router.callback_query(F.data == f"{prefix}:set_media")
    async def _set_media(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(BroadcastStates.waiting_media)
        prompt = await callback.message.answer("Пришлите фото или видео для рассылки (или /skip для пропуска):")
        await state.update_data(prompt_message_id=prompt.message_id)
        await callback.answer()

    @router.message(BroadcastStates.waiting_media)
    async def _process_media(message: Message, state: FSMContext, bot: Bot) -> None:
        media_id = media_type = None
        if message.photo:
            media_id, media_type = message.photo[-1].file_id, "photo"
        elif message.video:
            media_id, media_type = message.video.file_id, "video"
        elif message.text and message.text.strip() == "/skip":
            await state.update_data(media_id=None, media_type=None)
            await state.set_state(None)
            await _cleanup(message, state, bot, title, prefix, send_button_label)
            return
        else:
            await message.answer("Пожалуйста, отправьте фото или видео, либо /skip для пропуска.")
            return
        await state.update_data(media_id=media_id, media_type=media_type)
        await state.set_state(None)
        await _cleanup(message, state, bot, title, prefix, send_button_label)

    @router.callback_query(F.data == f"{prefix}:preview")
    async def _preview(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        text = data.get("text")
        if not text:
            await callback.answer("❗️ Сначала задайте текст.", show_alert=True)
            return
        markup = _make_markup(data.get("button_text"), data.get("button_url"))
        media_id, media_type = data.get("media_id"), data.get("media_type")
        if media_id and media_type == "photo":
            await callback.message.answer_photo(media_id, caption=text, reply_markup=markup)
        elif media_id and media_type == "video":
            await callback.message.answer_video(media_id, caption=text, reply_markup=markup)
        else:
            await callback.message.answer(text, reply_markup=markup)
        await callback.answer()

    @router.callback_query(F.data == f"{prefix}:send")
    async def _send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
        data = await state.get_data()
        text = data.get("text")
        if not text:
            await callback.answer("❗️ Пустое сообщение.", show_alert=True)
            return

        await callback.message.edit_text(start_status_text, reply_markup=back_button())
        asyncio.create_task(_send_task(bot, callback.from_user.id, data))
        await state.clear()
        await callback.answer()

    async def _send_task(bot: Bot, admin_id: int, data: dict) -> None:
        text = data.get("text")
        markup = _make_markup(data.get("button_text"), data.get("button_url"))
        media_id, media_type = data.get("media_id"), data.get("media_type")
        sent = failed = 0
        user_ids = await audience_fetcher()
        # Фильтрация VIP для рекламных рассылок (оптимизировано через asyncio.gather)
        if 'реклам' in title.lower() or 'ad' in prefix.lower():
            async with get_session() as session:
                is_vip_list = await asyncio.gather(*[_is_vip(session, uid) for uid in user_ids])
                user_ids = [uid for uid, is_vip in zip(user_ids, is_vip_list) if not is_vip]
        total = len(user_ids)
        logger.info(f"Начинается рассылка '{prefix}' для {total} пользователей.")
        # Прогресс-бар админу
        progress_msg = await bot.send_message(admin_id, _render_progress_bar(0, total))
        last_update = asyncio.get_event_loop().time()
        for user_id in user_ids:
            try:
                if media_id and media_type == "photo":
                    await bot.send_photo(user_id, media_id, caption=text, reply_markup=markup)
                elif media_id and media_type == "video":
                    await bot.send_video(user_id, media_id, caption=text, reply_markup=markup)
                else:
                    await bot.send_message(user_id, text, reply_markup=markup)
                sent += 1
            except TelegramAPIError as e:
                error_text = str(e)
                # Расширенное логирование причин ошибок
                if 'Too Many Requests' in error_text or 'FLOOD_WAIT' in error_text:
                    logger.error("FloodWait: превышен лимит Telegram при отправке %s: %s", user_id, error_text)
                elif 'bot was blocked by the user' in error_text:
                    logger.info("BotBlocked: пользователь %s заблокировал бота", user_id)
                elif 'chat not found' in error_text:
                    logger.info("ChatNotFound: чат %s не найден", user_id)
                elif 'user is deactivated' in error_text:
                    logger.info("UserDeactivated: пользователь %s деактивирован", user_id)
                else:
                    logger.warning("Не удалось отправить сообщение пользователю %s: %s", user_id, error_text)
                failed += 1
            except Exception as e:
                logger.error("Неизвестная ошибка при отправке пользователю %s: %s", user_id, e, exc_info=True)
                failed += 1
            # Обновлять прогресс не чаще, чем раз в BROADCAST_PROGRESS_UPDATE_INTERVAL секунд или каждые 100 сообщений
            now = asyncio.get_event_loop().time()
            if (sent % 100 == 0 or sent == total) or (now - last_update > BROADCAST_PROGRESS_UPDATE_INTERVAL):
                with suppress(TelegramAPIError):
                    await bot.edit_message_text(
                        text=_render_progress_bar(sent, total),
                        chat_id=admin_id,
                        message_id=progress_msg.message_id
                    )
                last_update = now
            await asyncio.sleep(BROADCAST_PER_MESSAGE_DELAY)
        logger.info("Рассылка '%s' завершена. Отправлено=%s Ошибок=%s", prefix, sent, failed)
        percent = int(sent / total * 100) if total else 0
        summary_text = (
            f"{summary_title}\n\n"
            f"👥 {total_label}: {total}\n"
            f"👍 Успешно отправлено: {sent} ({percent}%)\n"
            f"👎 Не удалось доставить: {failed}"
        )
        from aiogram.exceptions import TelegramBadRequest
        with suppress(TelegramBadRequest):
            await bot.edit_message_text(
                text=_render_progress_bar(sent, total),
                chat_id=admin_id,
                message_id=progress_msg.message_id
            )
        await bot.send_message(admin_id, summary_text, parse_mode="Markdown")

    async def _is_vip(session, uid):
        try:
            _, _, is_vip = await get_referral_stats(session, uid)
            return is_vip
        except Exception:
            return False

def _make_markup(button_text, button_url):
    if button_text and button_url:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=button_text, url=button_url)]])
    return None

async def _cleanup(message: Message, state: FSMContext, bot: Bot, title=None, prefix=None, send_button_label=None):
    """
    Универсальная функция: удаляет prompt и сообщение пользователя, при необходимости обновляет конструктор.
    Если переданы title/prefix/send_button_label — обновляет конструктор.
    """
    data = await state.get_data()
    prompt_msg_id = data.get("prompt_message_id")
    constructor_msg_id = data.get("constructor_message_id")
    with suppress(TelegramAPIError):
        if prompt_msg_id:
            await bot.delete_message(message.chat.id, prompt_msg_id)
        await message.delete()
    if title and prefix and send_button_label and constructor_msg_id:
        with suppress(TelegramAPIError):
            await bot.edit_message_text(
                text=title,
                chat_id=message.chat.id,
                message_id=constructor_msg_id,
                reply_markup=_keyboard(prefix, send_button_label),
                parse_mode="Markdown"
            )
