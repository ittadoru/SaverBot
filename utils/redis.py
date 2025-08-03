from datetime import date, timedelta
import redis.asyncio as redis
from aiogram import types, Bot
from utils import logger as log
from config import ADMINS, REDIS_URL
from datetime import timedelta
import re


r = redis.from_url(REDIS_URL, decode_responses=True)

async def add_user(user: types.User, bot: Bot):
    is_new = not await r.sismember("users", user.id)
    await r.sadd("users", user.id)
    await r.hset(f"user:{user.id}", mapping={
        "first_name": user.first_name or "",
        "username": user.username or ""
    })

    if is_new:
        log.log_message(f"🆕 Новый пользователь: {user.full_name} (@{user.username}) | id={user.id}", emoji="1️⃣")
        for admin_id in ADMINS:
            try:
                text = f"""👤 Новый пользователь:\n\nИмя: {user.first_name}\n@{user.username or 'Без username'}\n<pre>ID: {user.id}</pre>"""
                await bot.send_message(
                    admin_id,
                    text=text,
                    parse_mode="HTML"
                )
            except Exception as e:
                log.log_error(f"Не удалось отправить сообщение админу {admin_id}: {e}", user.username)


async def get_top_downloaders_all_time(limit=5):
    keys = await r.keys("downloads:user:*")
    top = []

    for key in keys:
        # Пропускаем ключи с датой (для 7-дневной статистики)
        if re.match(r"downloads:user:\d{4}-\d{2}-\d{2}:\d+", key):
            continue

        user_id = key.split(":")[-1]
        count = await r.get(key)
        top.append((int(user_id), int(count)))

    top.sort(key=lambda x: x[1], reverse=True)
    return top[:limit]

async def get_top_downloaders_last_7_days(limit=5):
    today = date.today()
    counters = {}

    for i in range(7):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        keys = await r.keys(f"downloads:user:{day_str}:*")

        for key in keys:
            parts = key.split(":")
            user_id = int(parts[-1])
            count = await r.get(key)
            counters[user_id] = counters.get(user_id, 0) + int(count)

    sorted_users = sorted(counters.items(), key=lambda x: x[1], reverse=True)
    return sorted_users[:limit]

async def increment_download(platform: str, user_id: int):
    await r.incr("downloads:total")
    await r.incr(f"downloads:{platform}")
    await r.incr(f"user:{user_id}:downloads")

    today_str = date.today().isoformat()
    key = f"downloads:user:{today_str}:{user_id}"
    await r.incr(key)
    await r.expire(key, 8 * 24 * 60 * 60)

async def log_user_activity(user_id: int):
    today_key = f"active_users:{date.today()}"
    await r.pfadd(today_key, user_id)
    await r.expire(today_key, 7 * 24 * 60 * 60)


async def push_recent_link(user_id: int, url: str):
    key = f"recent:links:{user_id}"
    await r.lpush(key, url)
    await r.ltrim(key, 0, 9)  # только 10 последних для этого пользователя

async def get_user_links(user_id: int) -> list[str]:
    key = f"recent:links:{user_id}"
    return await r.lrange(key, 0, 9)

# --- Подписчики ---

# Добавить/продлить подписку на days дней
import time
async def add_subscriber_with_duration(user_id: int, days: int):
    expire_key = f"subscriber:expire:{user_id}"
    now = int(time.time())
    current_expire = await r.get(expire_key)
    if current_expire and int(current_expire) > now:
        new_expire = int(current_expire) + days * 24 * 60 * 60
    else:
        new_expire = now + days * 24 * 60 * 60
    await r.set(expire_key, new_expire)
    await r.sadd("subscribers", user_id)

async def is_subscriber(user_id: int) -> bool:
    return await r.sismember("subscribers", user_id)

async def get_all_subscribers():
    return await r.smembers("subscribers")

# --- Счётчик скачиваний за день ---
async def increment_daily_download(user_id: int):
    key = f"downloads:user:{date.today().isoformat()}:{user_id}"
    await r.incr(key)
    await r.expire(key, 2 * 24 * 60 * 60)


# Получить количество скачиваний за день для пользователя
async def get_daily_downloads(user_id: int):
    key = f"downloads:user:{date.today().isoformat()}:{user_id}"
    return int(await r.get(key) or 0)

# Получить количество скачиваний за неделю для пользователя
async def get_weekly_downloads(user_id: int):
    today = date.today()
    total = 0
    for i in range(7):
        day = today - timedelta(days=i)
        key = f"downloads:user:{day.isoformat()}:{user_id}"
        count = await r.get(key)
        if count:
            total += int(count)
    return total

# Получить статистику скачиваний за день для всех пользователей
async def get_all_users_daily_stats():
    today = date.today().isoformat()
    keys = await r.keys(f"downloads:user:{today}:*")
    stats = {}
    for key in keys:
        user_id = int(key.split(":")[-1])
        stats[user_id] = int(await r.get(key) or 0)
    return stats

# Получить статистику скачиваний за неделю для всех пользователей
async def get_all_users_weekly_stats():
    today = date.today()
    stats = {}
    for i in range(7):
        day = today - timedelta(days=i)
        keys = await r.keys(f"downloads:user:{day.isoformat()}:*")
        for key in keys:
            user_id = int(key.split(":")[-1])
            stats[user_id] = stats.get(user_id, 0) + int(await r.get(key) or 0)
    return stats

# --- Статистика по платформам ---
async def increment_platform_download(user_id: int, platform: str):
    key = f"downloads:user:{user_id}:platform:{platform}"
    await r.incr(key)

async def get_platform_stats(user_id: int):
    keys = await r.keys(f"downloads:user:{user_id}:platform:*")
    stats = {}
    for key in keys:
        platform = key.split(":")[-1]
        stats[platform] = int(await r.get(key) or 0)
    return stats


# usernames отдельно не хранятся, поиск реализован через user:{id} хеши
async def get_user_id_by_username(username: str):
    user_ids = await r.smembers("users")
    for uid in user_ids:
        data = await r.hgetall(f"user:{uid}")
        if data.get("username", "").lower() == username.lower():
            return int(uid)
    return None

# Автоматическое уведомление пользователю при превышении лимита
async def notify_limit_exceeded(user_id: int, bot: Bot, limit: int):
    try:
        text = f"⚠️ Вы превысили лимит скачиваний ({limit} в сутки). Попробуйте завтра или оформите премиум!"
        await bot.send_message(user_id, text)
    except Exception as e:
        log.log_error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")


# --- Промокоды ---
# Добавить промокод (только админ)
async def add_promocode(code: str, duration_days: int = 30):
    # duration_days - срок действия подписки после активации
    await r.hset("promocodes", code, duration_days)

# Удалить промокод (только админ)
async def remove_promocode(code: str):
    await r.hdel("promocodes", code)

# Получить все промокоды
async def get_all_promocodes():
    return await r.hgetall("promocodes")


# Активация промокода пользователем с продлением подписки
import time
async def activate_promocode(user_id: int, code: str):
    duration = await r.hget("promocodes", code)
    if not duration:
        return False  # промокод не найден
    duration = int(duration)
    expire_key = f"subscriber:expire:{user_id}"
    now = int(time.time())
    current_expire = await r.get(expire_key)
    if current_expire and int(current_expire) > now:
        # Продлеваем существующую подписку
        new_expire = int(current_expire) + duration * 24 * 60 * 60
    else:
        # Новая подписка
        new_expire = now + duration * 24 * 60 * 60
    await r.set(expire_key, new_expire)
    await r.sadd("subscribers", user_id)
    await r.hdel("promocodes", code)  # промокод одноразовый
    return True

# Проверка и удаление подписчика по истечении срока
async def check_and_remove_expired_subscriber(user_id: int):
    expire_key = f"subscriber:expire:{user_id}"
    now = int(time.time())
    expire = await r.get(expire_key)
    if expire and int(expire) <= now:
        await r.srem("subscribers", user_id)
        await r.delete(expire_key)
        return True  # был удалён
    return False  # ещё активен или не подписчик
