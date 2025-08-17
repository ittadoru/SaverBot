"""Админ: управление списком требуемых каналов и глобальным ограничением."""
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from sqlalchemy.exc import ProgrammingError
from states.channels import ChannelStates
from aiogram.fsm.context import FSMContext

from config import ADMINS
from db.base import get_session
from db.channels import (
    list_channels,
    add_channel,
    delete_channel,
    toggle_channel_active,
    toggle_channel_required,
    is_channel_guard_enabled,
    toggle_channel_guard,
)

router = Router()
router.message.filter(F.from_user.id.in_(ADMINS))
router.callback_query.filter(F.from_user.id.in_(ADMINS))


async def _channels_menu_text(session) -> str:
    enabled = await is_channel_guard_enabled(session)
    channels = await list_channels(session)
    lines = [f"🌐 Глобальное ограничение: {'ON' if enabled else 'OFF'}", "", "Список каналов:"]
    if not channels:
        lines.append("— пока пусто")
    else:
        for ch in channels:
            lines.append(
                f"#{ch.id} @%s | %s | req=%s act=%s" % (
                    ch.username,
                    ch.title or '-',
                    '✅' if ch.is_required else '❌',
                    '✅' if ch.active else '❌'
                )
            )
    return '\n'.join(lines)


def _channels_menu_kb(channels, guard_on: bool):
    b = InlineKeyboardBuilder()
    for ch in channels:
        b.row(
            InlineKeyboardButton(text=f"@{ch.username}", callback_data=f"noop"),
            InlineKeyboardButton(text=("ON" if ch.active else "OFF"), callback_data=f"ch_toggle_act:{ch.id}"),
            InlineKeyboardButton(text="✖", callback_data=f"ch_del:{ch.id}"),
        )
    b.row(InlineKeyboardButton(text="➕ Добавить", callback_data="ch_add_start"))
    b.row(InlineKeyboardButton(text=("🌐 Выкл" if guard_on else "🌐 Вкл"), callback_data="ch_toggle_guard"))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))
    return b.as_markup()


@router.callback_query(F.data == "channels_menu")
async def show_channels_menu(callback: CallbackQuery):
    try:
        async with get_session() as session:
            channels = await list_channels(session)
            text = await _channels_menu_text(session)
            guard_on = await is_channel_guard_enabled(session)
        await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on))
    except ProgrammingError:
        await callback.message.edit_text(
            "Таблицы каналов ещё не созданы. Примените миграции (alembic upgrade head) или перезапустите контейнер app."
        )
    await callback.answer()


# --- Toggle handlers ---
@router.callback_query(F.data.startswith("ch_toggle_req:"))
async def toggle_required(callback: CallbackQuery):
    ch_id = int(callback.data.split(":", 1)[1])
    async with get_session() as session:
        await toggle_channel_required(session, ch_id)
        channels = await list_channels(session)
        text = await _channels_menu_text(session)
        guard_on = await is_channel_guard_enabled(session)
    await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on))
    await callback.answer()


@router.callback_query(F.data.startswith("ch_toggle_act:"))
async def toggle_active(callback: CallbackQuery):
    ch_id = int(callback.data.split(":", 1)[1])
    async with get_session() as session:
        await toggle_channel_active(session, ch_id)
        channels = await list_channels(session)
        text = await _channels_menu_text(session)
        guard_on = await is_channel_guard_enabled(session)
    await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on))
    await callback.answer()


@router.callback_query(F.data.startswith("ch_del:"))
async def delete_ch(callback: CallbackQuery):
    ch_id = int(callback.data.split(":", 1)[1])
    async with get_session() as session:
        await delete_channel(session, ch_id)
        channels = await list_channels(session)
        text = await _channels_menu_text(session)
        guard_on = await is_channel_guard_enabled(session)
    await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on))
    await callback.answer()


@router.callback_query(F.data == "ch_toggle_guard")
async def toggle_guard(callback: CallbackQuery):
    async with get_session() as session:
        await toggle_channel_guard(session)
        channels = await list_channels(session)
        text = await _channels_menu_text(session)
        guard_on = await is_channel_guard_enabled(session)
    await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on))
    await callback.answer()


# --- Add channel flow ---

@router.callback_query(F.data == "ch_add_start")
async def add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введите @username канала (перешлите сообщение из него — пока поддерживаем только @username):\n⬅️ /cancel для отмены"
    )
    await state.set_state(ChannelStates.waiting_for_username)
    await callback.answer()


# Обработчик текстового сообщения для добавления канала
@router.message(ChannelStates.waiting_for_username)
async def process_channel_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    if not username.isalnum():
        await message.answer("Некорректный username. Введите ещё раз или /cancel для отмены.")
        return
    async with get_session() as session:
        try:
            await add_channel(session, username)
            await message.answer(f"Канал @{username} добавлен.")
        except Exception as e:
            await message.answer(f"Ошибка при добавлении: {e}")
    await state.clear()
