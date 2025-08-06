from utils import logger as log
from redis import r, Tariff


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