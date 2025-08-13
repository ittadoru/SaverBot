from aiogram import Router, types
from aiogram.types import CallbackQuery
from redis.exceptions import RedisError
import datetime

from utils import logger as log
from config import ADMIN_ERROR
from redis_db import r

router = Router()


@router.callback_query(lambda c: c.data == "stats")
async def handle_stats(callback: CallbackQuery):
    try:
        total_downloads = await r.get("downloads:total") or 0
        yt_downloads = await r.get("downloads:youtube") or 0
        insta_downloads = await r.get("downloads:instagram") or 0
        tiktok_downloads = await r.get("downloads:tiktok") or 0

        total_users = await r.scard("users")
        today_key = f"active_users:{datetime.date.today()}"
        active_users_today = await r.pfcount(today_key)
        total_subscribers = len(await r.smembers("subscribers"))
    except Exception as e:
        log.log_error(f"Ошибка при получении статистики: {e}")
        await callback.message.answer("⚠️ Ошибка при получении статистики.")
        await callback.message.bot.send_message(ADMIN_ERROR, f"Ошибка при получении статистики: {e}")
        return await callback.answer()

    msg = (
        f"📊 <b>Статистика:</b>\n"
        f"👥 Уникальных пользователей: <b>{total_users}</b>\n"
        f"💎 С подпиской: <b>{total_subscribers}</b>\n"
        f"🟢 Активных сегодня: <b>{active_users_today}</b>\n"
        f"📥 Всего скачиваний: <b>{total_downloads}</b>\n\n"
        f"• YouTube: {yt_downloads}\n"
        f"• Instagram: {insta_downloads}\n"
        f"• TikTok: {tiktok_downloads}"
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
        ]
    )
    log.log_message("Админ запросил статистику", emoji="📊")
    await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


async def _get_top_users():
    """Вспомогательная функция для получения топа пользователей по скачиваниям."""
    user_ids = await r.smembers("users")
    users_with_counts = []

    for uid in user_ids:
        count = await r.get(f"user:{uid}:downloads")
        if count:
            users_with_counts.append((uid, int(count)))

    return sorted(users_with_counts, key=lambda x: x[1], reverse=True)[:10]


async def _format_top_message(top, title):
    """Форматирует сообщение с топом пользователей."""
    if not top:
        return None

    msg = f"{title}\n\n"
    for i, (uid, count) in enumerate(top, start=1):
        user_data = await r.hgetall(f"user:{uid}")
        username = user_data.get("username")
        name = user_data.get("first_name", "")
        line = f"{i}. {name}"
        if username:
            line += f" (@{username})"
        line += f" — {count} загрузок"
        msg += line + "\n"
    return msg


@router.callback_query(lambda c: c.data == "top_week")
async def handle_top_week(callback: CallbackQuery):
    try:
        top = await _get_top_users()
        msg = await _format_top_message(top, "🏆 <b>Топ пользователей за 7 дней:</b>")

        if not msg:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
                ]
            )
            log.log_message("Админ запросил топ пользователей за 7 дней, но данных нет", emoji="✖️")
            await callback.message.edit_text("Нет данных для отображения топа.", reply_markup=keyboard)
            return await callback.answer()

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
            ]
        )

        await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=keyboard)
        log.log_message("Админ запросил топ пользователей за 7 дней", emoji="🏆")
        await callback.answer()

    except Exception as e:
        await callback.message.answer("⚠️ Ошибка при получении топа.")
        log.log_error(f"Ошибка при получении топа: {e}")
        await callback.message.bot.send_message(ADMIN_ERROR, f"Ошибка при получении топа: {e}")
        return await callback.answer()


@router.callback_query(lambda c: c.data == "top_all")
async def handle_top_all(callback: CallbackQuery):
    try:
        top = await _get_top_users()
        msg = await _format_top_message(top, "🏅 <b>Топ за всё время:</b>")

        if not msg:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
                ]
            )
            log.log_message("Админ запросил топ пользователей за всё время, но данных нет", emoji="✖️")
            await callback.message.edit_text("Нет данных для отображения топа.", reply_markup=keyboard)
            return await callback.answer()

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
            ]
        )

        await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=keyboard)
        log.log_message("Админ запросил топ пользователей за всё время", emoji="🏅")
        await callback.answer()

    except Exception as e:
        await callback.message.answer("⚠️ Ошибка при получении топа.")
        log.log_error(f"Ошибка при получении топа: {e}")
        await callback.message.bot.send_message(ADMIN_ERROR, f"Ошибка при получении топа: {e}")
        return await callback.answer()