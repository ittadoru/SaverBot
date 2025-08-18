"""Старт: регистрация/обновление пользователя и выдача приветственного промокода новым."""

from __future__ import annotations

import logging
import random
from typing import Optional

from aiogram import Router, types
from aiogram.filters import Command

from db.base import get_session
from db.promocodes import add_promocode, get_promocode
from db.users import add_or_update_user, is_user_exists, log_user_activity

logger = logging.getLogger(__name__)


# --- Константы (нет «магических» чисел/строк в коде ниже) ---
PROMO_DURATION_DAYS = 7
PROMO_PREFIX = "WELCOME"
PROMO_RANDOM_MIN = 100_000
PROMO_RANDOM_MAX = 999_999
PROMO_MAX_TRIES = 5  # попыток сгенерировать уникальный код

router = Router()

async def _generate_unique_promocode(session, tries: int = PROMO_MAX_TRIES) -> Optional[str]:
    """Пытается создать и сохранить уникальный промокод, возвращает код или None.

    Проверяем коллизии через запрос существующего кода (быстро и просто).
    """
    for attempt in range(1, tries + 1):
        code = f"{PROMO_PREFIX}-{random.randint(PROMO_RANDOM_MIN, PROMO_RANDOM_MAX)}"
        exists = await get_promocode(session, code)
        if exists:
            continue
        await add_promocode(session, code, duration_days=PROMO_DURATION_DAYS)
        logger.info("Создан приветственный промокод %s (попытка %d)", code, attempt)
        return code
    logger.warning(
        "Не удалось сгенерировать уникальный промокод после %d попыток", tries
    )
    return None



@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    """
    Обрабатывает /start: добавляет/обновляет пользователя, логирует активность, даёт подарок новым, поддерживает рефералов.
    """
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username_raw = message.from_user.username or message.from_user.full_name
    username_display = username_raw or "пользователь"

    promo_code: Optional[str] = None
    is_new: bool = False
    referrer_id: Optional[int] = None


    # Обработка реферальной ссылки
    args = message.get_args() if hasattr(message, 'get_args') else ''
    if not args and message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2:
            args = parts[1]

    # Парсим referrer_id из args
    if args and args.startswith('ref_'):
        try:
            ref_id = int(args[4:])
            if ref_id != user_id:
                referrer_id = ref_id
        except Exception:
            pass

    async with get_session() as session:
        is_new = not await is_user_exists(session, user_id)
        # referrer_id только для новых пользователей
        user = await add_or_update_user(
            session, user_id, first_name=first_name, username=message.from_user.username, referrer_id=referrer_id if is_new else None
        )
        await log_user_activity(session, user_id)
        if is_new:
            promo_code = await _generate_unique_promocode(session)

    if is_new:
        if promo_code:
            promo_text = (
                f"В подарок тебе промокод на {PROMO_DURATION_DAYS} дней подписки: "
                f"<pre>{promo_code}</pre>\nАктивируй его через меню профиля (/profile).\n\n"
            )
        else:
            promo_text = ""
    else:
        promo_text = ""

    if is_new:
        logger.info("Новый пользователь %s (id=%s, referrer_id=%s) зарегистрирован", username_raw, user_id, referrer_id)
    else:
        logger.debug("Повторный старт пользователя id=%s", user_id)

    await message.answer(
        (
            f"👋 Привет, {username_display}!\n\n"
            f"{promo_text}"
            "Твой <b>профиль</b> со статистикой и лимитами всегда доступен через меню по команде /profile."
        ),
        parse_mode="HTML",
    )
