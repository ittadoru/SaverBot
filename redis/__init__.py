import redis.asyncio as redis

from config import REDIS_URL
from dataclasses import dataclass


@dataclass
class Tariff:
    id: int
    name: str
    price: int
    duration_days: int
    
# Инициализация Redis клиента с автоматическим декодированием строк
r = redis.from_url(REDIS_URL, decode_responses=True)

