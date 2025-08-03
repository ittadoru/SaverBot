# handlers/admin/stats.py

from aiogram import Router, types, F
from aiogram.types import CallbackQuery
from redis.exceptions import RedisError
import datetime
from utils import logger as log
from config import ADMIN_ERROR
from utils.redis import r

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
        await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        import traceback
        error_text = f"Ошибка: {e}"
        full_trace = traceback.format_exc()
        log.log_error(error_text)
        log.log_error(full_trace)
        # Отправка сообщения админу (замените на нужный ID)
        try:
            await callback.message.bot.send_message(
                ADMIN_ERROR,
                f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                parse_mode="HTML"
            )
        except Exception as send_err:
            log.log_error(f"Не удалось отправить ошибку админу: {send_err}")


@router.callback_query(lambda c: c.data == "top_week")
async def handle_top_week(callback: CallbackQuery):
    try:
        user_ids = await r.smembers("users")
        users_with_counts = []

        for uid in user_ids:
            count = await r.get(f"user:{uid}:downloads")
            if count:
                users_with_counts.append((uid, int(count)))

        # Сортируем по количеству скачиваний
        top = sorted(users_with_counts, key=lambda x: x[1], reverse=True)[:10]

        if not top:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
                ]
            )
            await callback.message.edit_text("Нет данных для отображения топа.", reply_markup=keyboard)
            return await callback.answer()

        msg = "🏆 <b>Топ пользователей за 7 дней:</b>\n\n"
        for i, (uid, count) in enumerate(top, start=1):
            user_data = await r.hgetall(f"user:{uid}")
            username = user_data.get("username")
            name = user_data.get("first_name", "")
            line = f"{i}. {name}"
            if username:
                line += f" (@{username})"
            line += f" — {count} загрузок"
            msg += line + "\n"

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
            ]
        )
        await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()

    except RedisError:
        await callback.message.answer("⚠️ Ошибка при получении топа.")
        await callback.answer()


@router.callback_query(lambda c: c.data == "top_all")
async def handle_top_all(callback: CallbackQuery):
    try:
        user_ids = await r.smembers("users")
        users_with_counts = []

        for uid in user_ids:
            count = await r.get(f"user:{uid}:downloads")
            if count:
                users_with_counts.append((uid, int(count)))

        top = sorted(users_with_counts, key=lambda x: x[1], reverse=True)[:10]

        if not top:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
                ]
            )
            await callback.message.edit_text("Нет данных для отображения топа.", reply_markup=keyboard)
            return await callback.answer()

        msg = "🏅 <b>Топ за всё время:</b>\n\n"
        for i, (uid, count) in enumerate(top, start=1):
            user_data = await r.hgetall(f"user:{uid}")
            username = user_data.get("username")
            name = user_data.get("first_name", "")
            line = f"{i}. {name}"
            if username:
                line += f" (@{username})"
            line += f" — {count} загрузок"
            msg += line + "\n"

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]
            ]
        )
        await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()

    except RedisError:
        await callback.message.answer("⚠️ Ошибка при получении топа.")
        await callback.answer()
