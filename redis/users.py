from datetime import date, timedelta
from redis import r
from aiogram import types, Bot
from config import ADMINS
from utils import logger as log


async def add_user(user: types.User, bot: Bot):
    """
    Добавляет пользователя в Redis, если он новый — уведомляет админов.
    """
    is_new = not await r.sismember("users", user.id)
    await r.sadd("users", user.id)
    await r.hset(
        f"user:{user.id}",
        mapping={"first_name": user.first_name or "", "username": user.username or ""},
    )

    if is_new:
        log.log_message(
            f"Новый пользователь: {user.full_name} (@{user.username}) | id={user.id}",
            emoji="1️⃣",
        )
        for admin_id in ADMINS:
            try:
                text = (
                    f"👤 Новый пользователь:\n\n"
                    f"Имя: {user.first_name}\n"
                    f"@{user.username or 'Без username'}\n"
                    f"<pre>ID: {user.id}</pre>"
                )
                await bot.send_message(admin_id, text=text, parse_mode="HTML")
            except Exception as e:
                log.log_error(
                    f"Не удалось отправить сообщение админу {admin_id}: {e}",
                    user.username,
                )

async def log_user_activity(user_id: int):
    """
    Добавить пользователя в HyperLogLog активных пользователей за сегодня.
    """
    today_key = f"active_users:{date.today()}"
    await r.pfadd(today_key, user_id)
    # Держим статистику 7 дней
    await r.expire(today_key, 7 * 24 * 60 * 60)

async def get_user_links(user_id: int) -> list[str]:
    """
    Получить последние ссылки пользователя.
    """
    key = f"recent:links:{user_id}"
    return await r.lrange(key, 0, 9)

async def get_all_users_daily_stats():
    """
    Получить статистику скачиваний за сегодня для всех пользователей.
    """
    today = date.today().isoformat()
    keys = await r.keys(f"downloads:user:{today}:*")
    stats = {}
    for key in keys:
        user_id = int(key.split(":")[-1])
        stats[user_id] = int(await r.get(key) or 0)
    return stats

async def get_all_users_weekly_stats():
    """
    Получить статистику скачиваний за последние 7 дней для всех пользователей.
    """
    today = date.today()
    stats = {}
    for i in range(7):
        day = today - timedelta(days=i)
        keys = await r.keys(f"downloads:user:{day.isoformat()}:*")
        for key in keys:
            user_id = int(key.split(":")[-1])
            stats[user_id] = stats.get(user_id, 0) + int(await r.get(key) or 0)
    return stats

async def get_user_id_by_username(username: str):
    """
    Найти user_id по username (регистр не важен).
    """
    user_ids = await r.smembers("users")
    for uid in user_ids:
        data = await r.hgetall(f"user:{uid}")
        if data.get("username", "").lower() == username.lower():
            return int(uid)
    return None

async def push_recent_link(user_id: int, url: str):
    """
    Сохранить последний URL пользователя (максимум 10).
    """
    key = f"recent:links:{user_id}"
    await r.lpush(key, url)
    await r.ltrim(key, 0, 9)  # сохраняем только 10 последних ссылок