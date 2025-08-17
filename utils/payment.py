"""Платежи YooKassa: создание платежа и парсинг webhook-уведомлений."""

from __future__ import annotations

import logging
import uuid
from typing import NamedTuple, Optional, Dict

from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification

from config import SHOP_ID, API_KEY

logger = logging.getLogger(__name__)

# --- Константы ---
CURRENCY = "RUB"
EMAIL_DOMAIN_FALLBACK = "example.local"  # Заглушка для чеков (при необходимости заменить)
MAX_DESCRIPTION_LEN = 128  # Практическое ограничение (YooKassa допускает больше, но держим короче)


class PaymentResult(NamedTuple):
    """Результат создания платежа: URL для оплаты и ID платежа."""
    url: str
    payment_id: str


def _ensure_configuration() -> None:
    """Гарантирует инициализацию SDK (контракт: SHOP_ID/API_KEY должны быть заданы)."""
    if not SHOP_ID or not API_KEY:
        raise RuntimeError("YooKassa credentials (SHOP_ID/API_KEY) не заданы")
    Configuration.account_id = SHOP_ID
    Configuration.secret_key = API_KEY


def _gen_idempotence_key() -> str:
    """Генерирует уникальный idempotence key (UUID4)."""
    return str(uuid.uuid4())


def create_payment(
    user_id: int,
    amount: int,
    description: str,
    bot_username: str,
    metadata: Optional[Dict[str, str]] = None,
    capture: bool = True,
) -> PaymentResult:
    """Создаёт платёж YooKassa.

    Contract:
      inputs: user_id>0, amount>0 (в рублях), непустой description (усекается до 128), bot_username без '@'
      returns: PaymentResult(url, payment_id)
      raises: ValueError (невалидные аргументы), RuntimeError (нет конфигурации), исключения SDK/сети (пробрасываются)
      guarantees: currency=RUB, сумма с 2 знаками, идемпотентность на уровне вызова (уникальный ключ)
    """
    if user_id <= 0:
        raise ValueError("user_id должен быть > 0")
    if amount <= 0:
        raise ValueError("amount должен быть > 0")
    if not description or not description.strip():
        raise ValueError("description не должен быть пустым")

    # Подготовка входных данных
    desc = description.strip()
    if len(desc) > MAX_DESCRIPTION_LEN:
        logger.debug("Описание платежа усечено с %d до %d", len(desc), MAX_DESCRIPTION_LEN)
        desc = desc[:MAX_DESCRIPTION_LEN]

    bot_name = bot_username.lstrip('@') if bot_username else "bot"
    value_str = f"{amount:.2f}"

    # Метаданные: копия + обязательные поля
    meta: Dict[str, str] = dict(metadata) if metadata else {}
    meta.setdefault("user_id", str(user_id))

    _ensure_configuration()
    idempotence_key = _gen_idempotence_key()

    receipt_data = {
        "customer": {
            # Минимально допустимый email-заглушка для чека.
            "email": f"user_{user_id}@{EMAIL_DOMAIN_FALLBACK}"
        },
        "items": [
            {
                "description": desc,
                "quantity": "1.00",
                "amount": {"value": value_str, "currency": CURRENCY},
                "vat_code": "1",  # НДС не облагается (адаптируйте при необходимости)
                "payment_mode": "full_prepayment",
                "payment_subject": "service",
            }
        ],
    }

    payload = {
        "amount": {"value": value_str, "currency": CURRENCY},
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{bot_name}",
        },
        "capture": capture,
        "description": desc,
        "metadata": meta,
        "receipt": receipt_data,
    }

    logger.debug(
        "Создание платежа: user_id=%s amount=%s desc='%s' meta_keys=%s",
        user_id, value_str, desc, list(meta.keys())
    )

    payment = Payment.create(payload, idempotence_key)

    logger.info(
        "Платеж создан: id=%s user=%s amount=%s capture=%s",
        payment.id, user_id, value_str, capture
    )
    return PaymentResult(payment.confirmation.confirmation_url, payment.id)


def parse_webhook_notification(request_body: dict) -> WebhookNotification | None:
    """Пытается распарсить webhook YooKassa; при ошибке возвращает None."""
    try:
        notification_object = WebhookNotification(request_body)
        return notification_object
    except Exception:  # noqa: BLE001
        logger.debug("Невалидное webhook-уведомление: %s", request_body)
        return None
