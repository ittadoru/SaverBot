"""Профиль пользователя: показ статуса подписки и базовой информации."""

from datetime import datetime
import logging
from aiogram import Router, types
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from db.base import get_session
from db.subscribers import get_subscriber_expiry

logger = logging.getLogger(__name__)

router = Router()


def _build_profile_keyboard() -> types.InlineKeyboardMarkup:
    """Возвращает клавиатуру профиля."""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 Купить подписку", callback_data="subscribe")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")],
        ]
    )


def _format_subscription_status(expire_at: datetime | None) -> str:
    """Возвращает человекочитаемый статус подписки."""
    if not expire_at:
        return "❌ Подписка не активна"
    now = datetime.now(expire_at.tzinfo)
    if expire_at > now:
        return f"✅ Подписка активна до <b>{expire_at.strftime('%d.%m.%Y %H:%M')}</b>"
    return "❌ Подписка истекла"


def _build_profile_text(user_id: int, name: str, username: str, status: str) -> str:
    """Формирует текст профиля."""
    username_part = f"@{username}" if username else "—"
    return (
        "<b>👤 Пользователь:</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Имя: {name}\n"
        f"{status}\n"
        f"Username: {username_part}\n"
    )


@router.callback_query(lambda c: c.data == "myprofile")
async def show_profile(callback: CallbackQuery) -> None:
    """Показывает профиль пользователя (кнопка myprofile)."""
    user_id = callback.from_user.id
    name = callback.from_user.first_name or "Без имени"
    username = callback.from_user.username or ""
    logger.debug("Открыт профиль пользователем user_id=%d", user_id)

    async with get_session() as session:
        expire_at = await get_subscriber_expiry(session, user_id)
    status = _format_subscription_status(expire_at)
    text = _build_profile_text(user_id, name, username, status)

    # Если текст уже такой же — не редактируем (чтобы не ловить ошибку)
    current = (callback.message.text or "").strip()
    if current == text.strip():
        await callback.answer()
        logger.debug("Профиль без изменений (user_id=%d)", user_id)
        return

    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=_build_profile_keyboard()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
            logger.debug(
                "Подавлена ошибка 'message is not modified' (user_id=%d)", user_id
            )
            return
        # На другие ошибки пусть видно в логах
        logger.exception("Не удалось обновить профиль user_id=%d", user_id)
        raise

    await callback.answer()
    logger.info("Профиль показан user_id=%d", user_id)
