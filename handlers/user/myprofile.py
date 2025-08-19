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
from config import DAILY_DOWNLOAD_LIMITS


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

def _build_referral_text(ref_count: int, level: int, to_next: str, progress_bar: str = "") -> str:
    level_names = {
        1: "1 (базовый)",
        2: "2 (1 реферал)",
        3: "3 (3 реферала, бонус)",
        4: "4 (10 рефералов, VIP)",
        5: "5 (30 рефералов, бессрочная подписка)"
    }
    return (
        f"\n\n<b>Реферальная программа:</b>\n"
        f"\n<b>Твой уровень:</b> {level_names.get(level, '—')}"
        f"\n<b>Рефералов:</b> {ref_count}"
        f"\n{progress_bar}"
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
        # Новая логика перехода между уровнями
        next_level_map = {1: 2, 2: 3, 3: 4, 4: 5, 5: None}
        next_level_reqs = {2: 1, 3: 3, 4: 10, 5: 30}
        prev_level_min = {1: 0, 2: 1, 3: 3, 4: 10, 5: 30}[level]
        next_level = next_level_map.get(level)
        if next_level:
            need = next_level_reqs[next_level] - prev_level_min
            have = max(0, ref_count - prev_level_min)
            to_next = f"До следующего уровня: {next_level_reqs[next_level] - ref_count} рефералов"
            # Прогресс-бар
            bar_len = 8
            filled = min(bar_len, int(bar_len * have / need)) if need > 0 else bar_len
            empty = bar_len - filled
            progress_bar = f"Прогресс: {'🟩'*filled}{'⬜️'*empty} ({have}/{need})"
        else:
            to_next = "Максимальный уровень!"
            progress_bar = ""

    # Если есть активная подписка — всегда безлимит
    now = datetime.now(expire_at.tzinfo) if expire_at else None
    if expire_at and expire_at > now:
        left = '∞'
    else:
        limit = DAILY_DOWNLOAD_LIMITS.get(level)
        if limit is None:
            left = '∞'
        else:
            left = max(0, limit - today)
    status = _format_subscription_status(expire_at)
    text = _build_profile_text(user_id, name, username, status, total, today, left, platform_stats)
    text += _build_referral_text(ref_count, level, to_next, progress_bar)

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
