import os

def get_rub_per_usdt() -> float:
    try:
        return float(os.getenv("RUB_PER_USDT", "90"))
    except Exception:
        return 90.0

async def rub_to_usdt(rub_amount: float) -> float:
    rate = get_rub_per_usdt()
    if rate <= 0:
        rate = 90.0
    usdt_amount = rub_amount / rate
    return max(round(usdt_amount, 2), 1.0)

async def usdt_to_rub(usdt_amount: float) -> float:
    rate = get_rub_per_usdt()
    if rate <= 0:
        rate = 90.0
    rub_amount = usdt_amount * rate
    return round(rub_amount, 2)