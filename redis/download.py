import re
from datetime import date, timedelta
from aiogram import Bot
from utils import logger as log
from redis import r

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