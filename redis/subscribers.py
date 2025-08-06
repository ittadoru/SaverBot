import time
from redis import r
from utils import logger as log

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