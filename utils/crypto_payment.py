import logging
from typing import NamedTuple

from loader import crypto_pay


logger = logging.getLogger(__name__)


class CryptoPaymentResult(NamedTuple):
    """Результат создания крипто-платежа: URL для оплаты и ID инвойса."""
    url: str
    invoice_id: int


async def create_crypto_payment(
    amount: float,
    asset: str,
    description: str,
    user_id: int,
    tariff_id: int,
) -> CryptoPaymentResult:
    """Создаёт инвойс в Crypto Pay."""
    try:
        invoice = await crypto_pay.create_invoice(
            asset=asset,
            amount=amount,
            description=description,
            payload=f"{user_id}:{tariff_id}"
        )
        logger.info(f"Создан крипто-инвойс {invoice.invoice_id} для пользователя {user_id}")
        return CryptoPaymentResult(url=invoice.bot_invoice_url, invoice_id=invoice.invoice_id)
    finally:
        await crypto_pay.close()
