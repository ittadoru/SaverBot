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
    """
    Формирует текст меню управления каналами с эмодзи и статусами.
    """
    enabled = await is_channel_guard_enabled(session)
    channels = await list_channels(session)
    lines = [
        f"🌐 Ограничение: {'ВКЛ' if enabled else 'ВЫКЛ'}",
        "",
        "📋 <b>Список каналов</b>:"
    ]
    if not channels:
        lines.append("— пока пусто")
    else:
        for ch in channels:
            lines.append(
                f"#{ch.id} @{ch.username} | {ch.title or '-'} | Обязателен: {'✅' if ch.is_required else '❌'} | Активен: {'✅' if ch.active else '❌'}"
            )
    return '\n'.join(lines)


def _channels_menu_kb(channels, guard_on: bool):
    """
    Формирует клавиатуру для меню каналов с эмодзи.
    """
    b = InlineKeyboardBuilder()
    for ch in channels:
        b.row(
            InlineKeyboardButton(text=f"📢 @{ch.username}", callback_data=f"noop"),
            InlineKeyboardButton(text=("🟢" if ch.active else "🔴"), callback_data=f"ch_toggle_act:{ch.id}"),
            InlineKeyboardButton(text="✖️", callback_data=f"ch_del:{ch.id}"),
        )
    b.row(InlineKeyboardButton(text="➕ Добавить", callback_data="ch_add_start"))
    b.row(InlineKeyboardButton(text=("🌐 Выкл" if guard_on else "🌐 Вкл"), callback_data="ch_toggle_guard"))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))
    return b.as_markup()


@router.callback_query(F.data == "channels_menu")
async def show_channels_menu(callback: CallbackQuery):
    """
    Показывает меню управления каналами с клавиатурой и статусами.
    """
    try:
        async with get_session() as session:
            channels = await list_channels(session)
            text = await _channels_menu_text(session)
            guard_on = await is_channel_guard_enabled(session)
        await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on), parse_mode="HTML")
    except ProgrammingError:
        await callback.message.edit_text(
            "⚠️ Таблицы каналов ещё не созданы. Примените миграции (alembic upgrade head) или перезапустите контейнер app."
        )
    await callback.answer()


# --- Toggle handlers ---
@router.callback_query(F.data.startswith("ch_toggle_req:"))
async def toggle_required(callback: CallbackQuery):
    """
    Переключает обязательность канала.
    """
    ch_id = int(callback.data.split(":", 1)[1])
    async with get_session() as session:
        await toggle_channel_required(session, ch_id)
        channels = await list_channels(session)
        text = await _channels_menu_text(session)
        guard_on = await is_channel_guard_enabled(session)
    await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ch_toggle_act:"))
async def toggle_active(callback: CallbackQuery):
    """
    Переключает активность канала.
    """
    ch_id = int(callback.data.split(":", 1)[1])
    async with get_session() as session:
        await toggle_channel_active(session, ch_id)
        channels = await list_channels(session)
        text = await _channels_menu_text(session)
        guard_on = await is_channel_guard_enabled(session)
    await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ch_del:"))
async def delete_ch(callback: CallbackQuery):
    """
    Удаляет канал из списка.
    """
    ch_id = int(callback.data.split(":", 1)[1])
    async with get_session() as session:
        await delete_channel(session, ch_id)
        channels = await list_channels(session)
        text = await _channels_menu_text(session)
        guard_on = await is_channel_guard_enabled(session)
    await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ch_toggle_guard")
async def toggle_guard(callback: CallbackQuery):
    """
    Включает или выключает глобальное ограничение.
    """
    async with get_session() as session:
        await toggle_channel_guard(session)
        channels = await list_channels(session)
        text = await _channels_menu_text(session)
        guard_on = await is_channel_guard_enabled(session)
    await callback.message.edit_text(text, reply_markup=_channels_menu_kb(channels, guard_on), parse_mode="HTML")
    await callback.answer()


# --- Add channel flow ---

@router.callback_query(F.data == "ch_add_start")
async def add_start(callback: CallbackQuery, state: FSMContext):
    """
    Запускает процесс добавления нового канала.
    """
    await callback.message.answer(
        "➕ Введите <b>@username</b> канала (или перешлите сообщение из него).\n\nДля отмены — /cancel"
    )
    await state.set_state(ChannelStates.waiting_for_username)
    await callback.answer()


# Обработчик текстового сообщения для добавления канала
@router.message(ChannelStates.waiting_for_username)
async def process_channel_username(message: Message, state: FSMContext):
    """
    Обрабатывает ввод username для добавления канала.
    """
    username = message.text.strip().lstrip("@")
    if not username.isalnum():
        await message.answer("❌ Некорректный username. Попробуйте ещё раз или /cancel для отмены.")
        return
    async with get_session() as session:
        try:
            await add_channel(session, username)
            await message.answer(f"✅ Канал <b>@{username}</b> успешно добавлен!")
        except Exception as e:
            await message.answer(f"⚠️ Ошибка при добавлении: {e}")
    await state.clear()
