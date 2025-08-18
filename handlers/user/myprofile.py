"""Профиль пользователя: показ статуса подписки и базовой информации."""

from datetime import datetime
import logging
from aiogram import Router, types
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from db.base import get_session
from db.subscribers import get_subscriber_expiry
from db.downloads import get_total_downloads, get_daily_downloads
from db.platforms import get_platform_counts, PLATFORMS
from handlers.user.referral import get_referral_stats


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
        if expire_at.year > 2124:
            return "✅ Подписка: <b>бессрочная</b>"
        return f"✅ Подписка активна до <b>{expire_at.strftime('%d.%m.%Y %H:%M')}</b>"
    return "❌ Подписка истекла"


def _build_profile_text(user_id: int, name: str, username: str, status: str, total: int, today: int, left: int, platform_stats: dict) -> str:
    username_part = f"@{username}" if username else "—"
    stats = (
        f"<b>👤 Пользователь:</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Имя: {name}\n"
        f"{status}\n"
        f"Username: {username_part}\n\n"
        f"<b>Ваша статистика:</b>\n"
        f"  • Всего скачиваний: <b>{total}</b>\n"
        f"  • Сегодня: <b>{today}</b> (осталось: <b>{left}</b>)\n"
    )
    stats += "  • По платформам:\n"
    for p in PLATFORMS:
        stats += f"    {p.title()}: <b>{platform_stats.get(p, 0)}</b>\n"
    return stats

def _build_referral_text(ref_count: int, level: int, to_next: str) -> str:
    level_names = {
        0: "Нет уровня",
        1: "1",
        2: "2 (увеличенный лимит)",
        3: "3 (VIP)",
        4: "4 (бессрочная подписка)"
    }
    return (
        f"\n<b>Реферальная программа:</b>"
        f"\n<b>Твой уровень:</b> {level_names[level]}"
        f"\n<b>Рефералов:</b> {ref_count}"
        f"\n{to_next}\n"
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
        total = await get_total_downloads(session, user_id)
        today = await get_daily_downloads(session, user_id)
        platform_stats = await get_platform_counts(session, user_id)
        # --- Реферальная информация ---
        ref_count, level, _ = await get_referral_stats(session, user_id)
        next_level = {0: 1, 1: 3, 2: 10, 3: 30, 4: None}[level]
        to_next = f"До следующего уровня: {next_level - ref_count} рефералов" if next_level else "Максимальный уровень!"

    left = max(0, 20 - today)
    status = _format_subscription_status(expire_at)
    text = _build_profile_text(user_id, name, username, status, total, today, left, platform_stats)
    text += _build_referral_text(ref_count, level, to_next)

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
        logger.exception("Не удалось обновить профиль user_id=%d", user_id)
        raise

    await callback.answer()
    logger.info("Профиль показан user_id=%d", user_id)
