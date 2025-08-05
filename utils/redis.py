import json
import re
import time
from datetime import date, timedelta

import redis.asyncio as redis
from aiogram import types, Bot

from config import ADMINS, REDIS_URL
from utils import logger as log
from dataclasses import dataclass


@dataclass
class Tariff:
    id: int
    name: str
    price: int
    duration_days: int
    
# Инициализация Redis клиента с автоматическим декодированием строк
r = redis.from_url(REDIS_URL, decode_responses=True)


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


async def get_top_downloaders_all_time(limit=5):
    """
    Получить топ пользователей по скачиваниям за всё время.
    """
    keys = await r.keys("downloads:user:*")
    top = []

    for key in keys:
        # Пропускаем ключи с датой (считаются отдельно для 7-дневной статистики)
        if re.match(r"downloads:user:\d{4}-\d{2}-\d{2}:\d+", key):
            continue

        user_id = key.split(":")[-1]
        count = await r.get(key)
        top.append((int(user_id), int(count)))

    top.sort(key=lambda x: x[1], reverse=True)
    return top[:limit]


async def get_top_downloaders_last_7_days(limit=5):
    """
    Получить топ пользователей по скачиваниям за последние 7 дней.
    """
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
    """
    Увеличить счетчик скачиваний (общий, по платформе и пользователя).
    """
    await r.incr("downloads:total")
    await r.incr(f"downloads:{platform}")
    await r.incr(f"user:{user_id}:downloads")

    today_str = date.today().isoformat()
    key = f"downloads:user:{today_str}:{user_id}"
    await r.incr(key)
    # Срок хранения — 8 дней (для еженедельной статистики)
    await r.expire(key, 8 * 24 * 60 * 60)


async def log_user_activity(user_id: int):
    """
    Добавить пользователя в HyperLogLog активных пользователей за сегодня.
    """
    today_key = f"active_users:{date.today()}"
    await r.pfadd(today_key, user_id)
    # Держим статистику 7 дней
    await r.expire(today_key, 7 * 24 * 60 * 60)


async def push_recent_link(user_id: int, url: str):
    """
    Сохранить последний URL пользователя (максимум 10).
    """
    key = f"recent:links:{user_id}"
    await r.lpush(key, url)
    await r.ltrim(key, 0, 9)  # сохраняем только 10 последних ссылок


async def get_user_links(user_id: int) -> list[str]:
    """
    Получить последние ссылки пользователя.
    """
    key = f"recent:links:{user_id}"
    return await r.lrange(key, 0, 9)


# --- Подписчики ---

async def add_subscriber_with_duration(user_id: int, days: int):
    """
    Добавить или продлить подписку пользователя на указанное количество дней.
    """
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
    """
    Проверить, является ли пользователь подписчиком.
    """
    return await r.sismember("subscribers", user_id)


async def get_all_subscribers():
    """
    Получить всех подписчиков.
    """
    return await r.smembers("subscribers")


# Создание тарифа
async def create_tariff(name: str, price: int, duration_days: int):
    # Генерируем новый уникальный ID, например, увеличиваем максимальный из уже существующих
    existing_ids = await r.smembers("tariffs")
    if existing_ids:
        new_id = max(int(i) for i in existing_ids) + 1
    else:
        new_id = 1

    key = f"tariff:{new_id}"
    await r.hset(key, mapping={
        "id": new_id,
        "name": name,
        "price": price,
        "duration_days": duration_days
    })
    await r.sadd("tariffs", new_id)
    return new_id

async def delete_tariff(tariff_id: int):
    key = f"tariff:{tariff_id}"
    await r.delete(key)
    await r.srem("tariffs", tariff_id)


# Получение тарифа по ID
async def get_tariff_by_id(tariff_id: int) -> Tariff | None:
    key = f"tariff:{tariff_id}"
    data = await r.hgetall(key)
    if not data:
        return None

    return Tariff(
        id=int(data["id"]),
        name=data["name"],
        price=int(float(data["price"])),
        duration_days=int(data["duration_days"])
    )


# Получить все тарифы (опционально)
async def get_all_tariffs() -> list[Tariff]:
    ids = await r.smembers("tariffs")
    tariffs = []

    for tariff_id in ids:
        tariff = await get_tariff_by_id(int(tariff_id))
        if tariff:
            tariffs.append(tariff)

    return tariffs


async def increment_daily_download(user_id: int):
    """
    Увеличить счетчик скачиваний пользователя за сегодня.
    """
    key = f"downloads:user:{date.today().isoformat()}:{user_id}"
    await r.incr(key)
    # Храним 2 дня, чтобы избежать ранних удалений
    await r.expire(key, 2 * 24 * 60 * 60)


async def get_daily_downloads(user_id: int):
    """
    Получить количество скачиваний пользователя за сегодня.
    """
    key = f"downloads:user:{date.today().isoformat()}:{user_id}"
    return int(await r.get(key) or 0)


async def get_weekly_downloads(user_id: int):
    """
    Получить количество скачиваний пользователя за последние 7 дней.
    """
    today = date.today()
    total = 0
    for i in range(7):
        day = today - timedelta(days=i)
        key = f"downloads:user:{day.isoformat()}:{user_id}"
        count = await r.get(key)
        if count:
            total += int(count)
    return total


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


# --- Статистика по платформам ---

async def increment_platform_download(user_id: int, platform: str):
    """
    Увеличить счетчик скачиваний по платформе для пользователя.
    """
    key = f"downloads:user:{user_id}:platform:{platform}"
    await r.incr(key)


async def get_platform_stats(user_id: int):
    """
    Получить статистику скачиваний по платформам для пользователя.
    """
    keys = await r.keys(f"downloads:user:{user_id}:platform:*")
    stats = {}
    for key in keys:
        platform = key.split(":")[-1]
        stats[platform] = int(await r.get(key) or 0)
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


async def notify_limit_exceeded(user_id: int, bot: Bot, limit: int):
    """
    Уведомить пользователя о превышении лимита скачиваний.
    """
    try:
        text = (
            f"⚠️ Вы превысили лимит скачиваний ({limit} в сутки). "
            "Попробуйте завтра или оформите премиум!"
        )
        await bot.send_message(user_id, text)
    except Exception as e:
        log.log_error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")


# --- Промокоды ---

async def add_promocode(code: str, duration_days: int = 30):
    """
    Добавить промокод с указанным сроком действия (в днях).
    """
    await r.hset("promocodes", code, duration_days)


async def remove_promocode(code: str):
    """
    Удалить промокод.
    """
    await r.hdel("promocodes", code)


async def get_all_promocodes():
    """
    Получить все промокоды.
    """
    return await r.hgetall("promocodes")


async def activate_promocode(user_id: int, code: str):
    """
    Активировать промокод для пользователя (удалить код из списка).
    """
    duration = await r.hget("promocodes", code)
    if not duration:
        return None
    await add_subscriber_with_duration(user_id, int(duration))
    await remove_promocode(code)
    return int(duration)


# --- Поддержка (тикеты) ---

async def create_ticket(user_id: int, username: str, message: str):
    """
    Создать новую тему поддержки с сообщением.
    """
    topic_key = f"support:topic:{user_id}"
    topic = await r.get(topic_key)
    if topic:
        # Тикет уже существует
        return False

    data = {
        "user_id": user_id,
        "username": username,
        "messages": [message],
        "created_at": int(time.time()),
    }
    await r.set(topic_key, json.dumps(data))
    return True


async def add_message_to_ticket(user_id: int, message: str):
    """
    Добавить сообщение в существующий тикет.
    """
    topic_key = f"support:topic:{user_id}"
    topic_json = await r.get(topic_key)
    if not topic_json:
        return False

    topic = json.loads(topic_json)
    topic["messages"].append(message)
    await r.set(topic_key, json.dumps(topic))
    return True


async def get_ticket_messages(user_id: int):
    """
    Получить все сообщения из тикета пользователя.
    """
    topic_key = f"support:topic:{user_id}"
    topic_json = await r.get(topic_key)
    if not topic_json:
        return []

    topic = json.loads(topic_json)
    return topic.get("messages", [])


async def close_ticket(user_id: int):
    """
    Закрыть и удалить тикет.
    """
    topic_key = f"support:topic:{user_id}"
    await r.delete(topic_key)


