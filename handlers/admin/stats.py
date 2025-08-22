"""Статистика админа: агрегированные метрики пользователей, подписок и промокодов."""
from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

import logging
from db.base import get_session
from db.promocodes import get_active_promocodes_count
from db.platforms import get_top_platform_downloads
from db.subscribers import (
    get_subscriptions_count_for_period,
    get_total_subscribers,
)
from db.users import (
    get_active_users_today,
    get_new_users_count_for_period, get_total_users
)

router = Router()


@router.callback_query(F.data == "stats")
async def handle_stats(callback: CallbackQuery) -> None:
    """
    Собирает, форматирует и отображает расширенную статистику по боту с дружелюбным тоном и эмодзи.
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
            "⚠️ Произошла ошибка при получении статистики. Пожалуйста, попробуйте позже!",
            show_alert=True
        )
        return

    sub_percentage = (total_subscribers / total_users * 100) if total_users > 0 else 0

    text = (
        "<b>📊 Статистика SaverBot</b>\n\n"
        "<b>👥 Пользователи:</b> <b>{total_users}</b>\n"
        "<b>💎 Подписчики:</b> <b>{total_subscribers}</b> ({sub_percentage:.2f}%)\n"
        "<b>🎟️ Активных промокодов:</b> <b>{active_promos}</b>\n\n"
        "<b>🟢 Активны сегодня:</b> <b>{active_today}</b>\n"
        "<b>➕ Новых за 24ч:</b> <b>{new_today}</b>\n"
        "<b>➕ Новых за 7д:</b> <b>{new_week}</b>\n"
        "<b>➕ Новых за 30д:</b> <b>{new_month}</b>\n\n"
        "<b>📈 Подписки:</b>\n"
        " └ За 24ч: <b>{subs_today}</b>\n"
        " └ За 7д: <b>{subs_week}</b>\n"
        " └ За 30д: <b>{subs_month}</b>\n\n"
    ).format(
        total_users=total_users,
        total_subscribers=total_subscribers,
        sub_percentage=sub_percentage,
        active_promos=active_promos,
        active_today=active_today,
        new_today=new_today,
        new_week=new_week,
        new_month=new_month,
        subs_today=subs_today,
        subs_week=subs_week,
        subs_month=subs_month,
    )

    text += "<b>🏆 Топ скачиваний по платформам:</b>\n"
    platform_emojis = {"youtube": "▶️ YouTube", "tiktok": "🎵 TikTok", "instagram": "📸 Instagram"}
    for platform in ["youtube", "tiktok", "instagram"]:
        count = top_downloads.get(platform, 0)
        text += f"{platform_emojis[platform]}: <b>{count}</b>\n"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_menu"))

    logging.info(f"Админ {callback.from_user.id} запросил расширенную статистику.")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()
