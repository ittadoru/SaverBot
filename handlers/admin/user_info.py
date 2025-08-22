"""Админ: поиск пользователя по ID/username и показ карточки."""

import logging
from datetime import datetime, timezone
from typing import Optional

from aiogram import Bot, F, Router, types
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMINS
from db import subscribers as db_subscribers
from db import users as db_users
from db import downloads as db_downloads
from db.base import get_session
from db.users import User
from states.history import HistoryStates


router = Router()
router.message.filter(F.from_user.id.in_(ADMINS))
router.callback_query.filter(F.from_user.id.in_(ADMINS))


class UserCallback(CallbackData, prefix="user_admin"):
    """Фабрика колбэков для действий с пользователем в админ-панели."""

    action: str
    user_id: int


@router.callback_query(F.data == "user_history_start")
async def show_user_history_prompt(
    callback: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Запрашивает у администратора ID или username для поиска пользователя.
    Изменяет текущее сообщение и сохраняет его ID для последующего редактирования.
    """
    await state.set_state(HistoryStates.waiting_for_id_or_username)
    await state.update_data(message_to_edit=callback.message.message_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="manage_users")

    await callback.message.edit_text(
        "<b>🔍 Поиск пользователя</b>\n\nПожалуйста, введите <b>ID</b> или <b>username</b> пользователя для поиска.\n\n<i>Для отмены — кнопка 'Назад'.</i>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.message(HistoryStates.waiting_for_id_or_username)
async def process_user_lookup(message: types.Message, state: FSMContext, bot: Bot) -> None:
    """
    Обрабатывает введенный ID/username, находит пользователя и выводит информацию о нём.
    Удаляет сообщение администратора и изменяет исходное, превращая его в инфо-карточку.
    """
    data = await state.get_data()
    message_id_to_edit: Optional[int] = data.get("message_to_edit")
    await state.clear()

    user_identifier = message.text.strip()
    user: Optional[User] = None

    await message.delete()

    async with get_session() as session:
        if user_identifier.isdigit():
            user = await db_users.get_user_by_id(session, int(user_identifier))
        else:
            username = user_identifier.lstrip("@").lower()
            user = await db_users.get_user_by_username(session, username)

        if not user:
            builder = InlineKeyboardBuilder()
            builder.button(text="⬅️ Назад", callback_data="manage_users")
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message_id_to_edit,
                text="❌ <b>Пользователь не найден.</b>\n\nПроверьте корректность ID или username.",
                parse_mode="HTML",
                reply_markup=builder.as_markup(),
            )
            return

        expiry_date = await db_subscribers.get_subscriber_expiry(session, user.id)
        now_utc = datetime.now(timezone.utc)
        if expiry_date and expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

        if expiry_date and expiry_date > now_utc:
            subscription_status = f"✅ Активна до <b>{expiry_date.strftime('%d.%m.%Y %H:%M')}</b> UTC"
        else:
            subscription_status = "❌ Не активна"

        last_links = await db_downloads.get_last_links(session, user.id, limit=3)
        links_block = "\n".join(last_links) if last_links else "(нет недавних ссылок)"

        user_info_text = (
            f"<b>👤 Карточка пользователя</b>\n\n"
            f"<b>ID:</b> <code>{user.id}</code>\n"
            f"<b>Имя:</b> {user.first_name or 'не указано'}\n"
            f"<b>Username:</b> {f'@{user.username}' if user.username else 'не указан'}\n"
            f"<b>Зарегистрирован:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"<b>Подписка:</b> {subscription_status}\n\n"
            f"<b>Последние 3 ссылки:</b>\n<pre>{links_block}</pre>"
        )

    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑️ Удалить пользователя",
        callback_data=UserCallback(action="delete", user_id=user.id).pack(),
    )
    builder.button(text="⬅️ Назад к списку", callback_data="manage_users")
    builder.adjust(1)

    await bot.edit_message_text(
        text=user_info_text,
        chat_id=message.chat.id,
        message_id=message_id_to_edit,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

@router.callback_query(UserCallback.filter(F.action == "delete"))
async def delete_user_handler(
    callback: types.CallbackQuery, callback_data: UserCallback
) -> None:
    """
    Обрабатывает удаление пользователя и возвращает в меню управления пользователями.
    """
    user_id_to_delete = callback_data.user_id
    admin_id = callback.from_user.id

    async with get_session() as session:
        success = await db_users.delete_user_by_id(session, user_id_to_delete)

    # Создаем клавиатуру меню управления пользователями
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Все пользователи", callback_data="all_users")
    builder.button(
        text="🔍 Данные пользователя", callback_data="user_history_start"
    )
    builder.button(
        text="🗑️ Удалить всех пользователей", callback_data="delete_all_users"
    )
    builder.button(text="⬅️ Назад", callback_data="admin_menu")
    builder.adjust(1)

    if success:
        logging.info(
            "Администратор %d удалил пользователя %d", admin_id, user_id_to_delete
        )
        text = f"✅ <b>Пользователь <code>{user_id_to_delete}</code> успешно удалён!</b>\n\nВыберите действие:"
    else:
        logging.warning(
            "Администратор %d не смог удалить несуществующего пользователя %d",
            admin_id,
            user_id_to_delete,
        )
        text = f"❌ <b>Не удалось найти и удалить пользователя <code>{user_id_to_delete}</code>.</b>\n\nВыберите действие:"

    await callback.message.edit_text(
        text=text, reply_markup=builder.as_markup(), parse_mode="HTML"
    )
    await callback.answer()
