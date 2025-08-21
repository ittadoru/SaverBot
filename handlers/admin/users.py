"""Админ: список пользователей, пагинация и (массовое) удаление."""

import logging
from math import ceil

from aiogram import F, Router, types
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from utils.keyboards import pagination_keyboard, back_button
from sqlalchemy.ext.asyncio import AsyncSession

from config import ADMINS
from db.base import get_session
from db.subscribers import is_subscriber
from db.users import (delete_user_by_id, get_all_user_ids, get_total_users,
                    get_users_by_ids)

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.from_user.id.in_(ADMINS))
router.callback_query.filter(F.from_user.id.in_(ADMINS))

USERS_PER_PAGE = 10


class UsersPageCallback(CallbackData, prefix="users_page"):
    """Фабрика колбэков для пагинации пользователей."""

    page: int


class ConfirmDeleteAllCallback(CallbackData, prefix="confirm_delete_all"):
    """Фабрика колбэков для подтверждения удаления всех пользователей."""

    confirm: bool

async def manage_users_menu(callback: types.CallbackQuery):
    """Отображает меню управления пользователями."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Все пользователи", callback_data="all_users"))
    builder.row(InlineKeyboardButton(text="🏆 Топ рефералов", callback_data="top_referrals"))
    builder.row(InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="user_history_start"))
    builder.row(InlineKeyboardButton(text="🗑️ Удалить всех", callback_data="delete_all_users"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    await callback.message.edit_text(
        "👥 <b>Пользователи</b>\n\nВыберите действие:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


async def _get_users_page_markup(session: AsyncSession, page: int = 1) -> tuple[str, InlineKeyboardBuilder]:
    """
    Возвращает текст и клавиатуру для страницы пользователей. Упрощённая и дружелюбная версия.
    """
    total_users = await get_total_users(session)
    total_pages = max(1, ceil(total_users / USERS_PER_PAGE))
    offset = (page - 1) * USERS_PER_PAGE

    user_ids = await get_all_user_ids(session, limit=USERS_PER_PAGE, offset=offset)
    users = await get_users_by_ids(session, user_ids)

    if not users:
        text = "❌ <b>Пользователей пока нет.</b>"
    else:
        text = "<b>👥 Список пользователей</b>\n\n"
        for user in users:
            is_sub = await is_subscriber(session, user.id)
            status_icon = "💎" if is_sub else "❌"
            username = f" (@{user.username})" if user.username else ""
            text += f"{status_icon} <code>{user.id}</code> — {user.first_name}{username}\n"

    nav = pagination_keyboard(page, total_pages, prefix="users_page", extra_buttons=[("⬅️ Назад", "manage_users")])
    return text, nav


@router.callback_query(F.data == "all_users")
async def list_users_handler(callback: types.CallbackQuery) -> None:
    """
    Показывает первую страницу списка всех пользователей с пагинацией и дружелюбным текстом.
    """
    async with get_session() as session:
        text, builder = await _get_users_page_markup(session, page=1)
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder
        )
    logger.info("Администратор %d запросил список пользователей.", callback.from_user.id)
    await callback.answer()


@router.callback_query(UsersPageCallback.filter())
async def paginate_users_handler(callback: types.CallbackQuery, callback_data: UsersPageCallback) -> None:
    """
    Обрабатывает переключение страниц списка пользователей.
    """
    page = callback_data.page
    async with get_session() as session:
        text, builder = await _get_users_page_markup(session, page)
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=builder.as_markup()
        )
    logger.info(
        "Администратор %d переключил страницу пользователей на %d.",
        callback.from_user.id,
        page,
    )
    await callback.answer()


@router.callback_query(F.data == "delete_all_users")
async def confirm_delete_all_users_handler(callback: types.CallbackQuery) -> None:
    """
    Запрашивает подтверждение на удаление всех пользователей с дружелюбным текстом и эмодзи.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑️ Да, удалить всех!",
        callback_data=ConfirmDeleteAllCallback(confirm=True).pack(),
    )
    builder.button(
        text="❌ Отмена", callback_data=ConfirmDeleteAllCallback(confirm=False).pack()
    )
    builder.adjust(1)
    await callback.message.edit_text(
        "<b>⚠️ Вы уверены, что хотите удалить <u>ВСЕХ</u> пользователей?</b>\n\n"
        "Это действие <b>необратимо</b> и приведёт к полной потере данных о пользователях и их подписках.",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(ConfirmDeleteAllCallback.filter())
async def delete_all_users_handler(callback: types.CallbackQuery, callback_data: ConfirmDeleteAllCallback) -> None:
    """
    Обрабатывает подтверждение или отмену удаления всех пользователей, дружелюбно и с эмодзи.
    """
    if not callback_data.confirm:
        await manage_users_menu(callback)
        return

    async with get_session() as session:
        user_ids = await get_all_user_ids(session)
        for uid in user_ids:
            await delete_user_by_id(session, uid)

    logger.warning(
        "Администратор %d удалил ВСЕХ пользователей.", callback.from_user.id
    )
    await callback.answer("✅ <b>Все пользователи были успешно удалены!</b>", show_alert=True)
    await callback.message.delete()

