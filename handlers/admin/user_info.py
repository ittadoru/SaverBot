"""Админ: поиск пользователя по ID/username и показ карточки."""

import logging
from datetime import datetime, timezone, timedelta
import html
from typing import Optional

from aiogram import Bot, F, Router, types
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMINS
from db import users as db_users
from db import downloads as db_downloads
from db import tokens as db_tokens
from db.base import get_session
from db.users import User
from config import SOCIAL_DAILY_LIMIT
from states.history import HistoryStates


logger = logging.getLogger(__name__)

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

        snapshot = await db_tokens.get_token_snapshot(session, user.id, refresh_daily=True)
        social_used = await db_tokens.get_daily_social_usage(session, user.id)
        social_left = max(0, SOCIAL_DAILY_LIMIT - social_used)

        # Получаем последние 3 ссылки с временем создания
        last_links = await db_downloads.get_last_links(session, user.id, limit=3, include_time=True)
        if last_links:
            # Формат: ссылка\nDD.MM.YYYY HH:MM MSK — <relative>\n\n
            msk = timezone(timedelta(hours=3))
            now_msk = datetime.now(timezone.utc).astimezone(msk)

            def _human_delta(seconds: int) -> str:
                if seconds < 60:
                    return "только что"
                minutes = seconds // 60
                if minutes < 60:
                    return f"{minutes} мин. назад"
                hours = minutes // 60
                if hours < 24:
                    return f"{hours} ч. назад"
                days = hours // 24
                if days < 30:
                    return f"{days} дн. назад"
                months = days // 30
                if months < 12:
                    return f"{months} мес. назад"
                years = months // 12
                return f"{years} г. назад"

            parts: list[str] = []
            for url, created_at in last_links:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                created_msk = created_at.astimezone(msk)
                time_str = created_msk.strftime('%d.%m.%Y %H:%M') + ' MSK'
                rel = _human_delta(int((now_msk - created_msk).total_seconds()))
                url_esc = html.escape(url, quote=True)
                parts.append(f"<a href=\"{url_esc}\">{url_esc}</a>\n<code>{time_str} — {rel}</code>\n")

            links_block = "\n".join(parts)
        else:
            links_block = "(нет недавних ссылок)"

        user_info_text = (
            f"<b>👤 Карточка пользователя</b>\n\n"
            f"<b>ID:</b> <code>{user.id}</code>\n"
            f"<b>Имя:</b> {user.first_name or 'не указано'}\n"
            f"<b>Username:</b> {f'@{user.username}' if user.username else 'не указан'}\n"
            f"<b>Зарегистрирован:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"<b>Токены:</b> {snapshot.total_tokens} (daily {snapshot.daily_tokens}, bonus {snapshot.bonus_tokens})\n"
            f"<b>tokenX:</b> {snapshot.token_x}\n"
            f"<b>Tiktok/Insta осталось сегодня:</b> {social_left}/{SOCIAL_DAILY_LIMIT}\n\n"
            f"<b>Последние 3 ссылки:</b>\n<pre>{links_block}</pre>"
        )
        await session.commit()

    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑️ Удалить",
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
        logger.info(
            "Администратор %d удалил пользователя %d", admin_id, user_id_to_delete
        )
        text = f"✅ <b>Пользователь <code>{user_id_to_delete}</code> успешно удалён!</b>\n\nВыберите действие:"
    else:
        logger.warning(
            "Администратор %d не смог удалить несуществующего пользователя %d",
            admin_id,
            user_id_to_delete,
        )
        text = f"❌ <b>Не удалось найти и удалить пользователя <code>{user_id_to_delete}</code>.</b>\n\nВыберите действие:"

    await callback.message.edit_text(
        text=text, reply_markup=builder.as_markup(), parse_mode="HTML"
    )
    await callback.answer()
