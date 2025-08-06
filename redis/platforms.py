from redis import r
from utils import logger as log

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