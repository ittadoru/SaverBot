"""Статистика админа: агрегированные метрики пользователей, подписок и промокодов."""

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

from db.base import get_session
from db.promocodes import get_active_promocodes_count
from db.subscribers import (
    get_subscriptions_count_for_period,
    get_total_subscribers,
)
from db.users import (
    get_active_users_today,
    get_new_users_count_for_period, get_total_users
)
from db.platforms import get_top_platform_downloads

router = Router()


@router.callback_query(F.data == "stats")
async def handle_stats(callback: CallbackQuery):
    """
    Собирает, форматирует и отображает расширенную статистику по боту.
    """
    try:
        async with get_session() as session:
            # --- Общая статистика ---
            total_users = await get_total_users(session)
            total_subscribers = await get_total_subscribers(session)
            active_promos = await get_active_promocodes_count(session)

            # --- Активность пользователей ---
            active_today = await get_active_users_today(session)
            new_today = await get_new_users_count_for_period(session, days=1)
            new_week = await get_new_users_count_for_period(session, days=7)
            new_month = await get_new_users_count_for_period(session, days=30)

            # --- Динамика подписок ---
            subs_today = await get_subscriptions_count_for_period(session, days=1)
            subs_week = await get_subscriptions_count_for_period(session, days=7)
            subs_month = await get_subscriptions_count_for_period(session, days=30)

            # --- Топ скачиваний по платформам ---
            top_downloads = await get_top_platform_downloads(session)

    except Exception as e:
        logging.error(f"Ошибка при получении статистики: {e}", exc_info=True)
        await callback.answer(
            "⚠️ Ошибка при получении статистики. Подробности в логах.",
            show_alert=True
        )
        return

    # --- Расчеты ---
    sub_percentage = (total_subscribers / total_users * 100) if total_users > 0 else 0

    # --- Форматирование текста ---
    text = (
        f"📊 <b>Расширенная статистика</b>\n\n"
        f"<b><u>Общая информация:</u></b>\n"
        f"  👥 Всего пользователей: <b>{total_users}</b>\n"
        f"  💎 Всего подписчиков: <b>{total_subscribers}</b> ({sub_percentage:.2f}%)\n"
        f"  🎟 Активных промокодов: <b>{active_promos}</b>\n\n"
        f"<b><u>Активность пользователей:</u></b>\n"
        f"  🟢 Активных сегодня: <b>{active_today}</b>\n"
        f"  ➕ Новых за 24 часа: <b>{new_today}</b>\n"
        f"  ➕ Новых за 7 дней: <b>{new_week}</b>\n"
        f"  ➕ Новых за 30 дней: <b>{new_month}</b>\n\n"
        f"<b><u>Динамика подписок (новых/продлений):</u></b>\n"
        f"  📈 За 24 часа: <b>{subs_today}</b>\n"
        f"  📈 За 7 дней: <b>{subs_week}</b>\n"
        f"  📈 За 30 дней: <b>{subs_month}</b>\n\n"
    )

    # --- Топ скачиваний по платформам ---
    def format_top(platform, count):
        return f"<b>{platform.title()}:</b> <b>{count}</b>"

    text += "<b><u>Топ скачиваний по платформам:</u></b>\n"
    for platform in ["youtube", "tiktok", "instagram"]:
        text += format_top(platform, top_downloads.get(platform, 0)) + "\n"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    logging.info(f"Админ {callback.from_user.id} запросил расширенную статистику.")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()
