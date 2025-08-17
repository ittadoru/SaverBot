"""Точка входа: инициализация логирования, создание бота/DP и запуск polling."""

from __future__ import annotations

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import register_handlers
from utils.logger import setup_logger

logger = logging.getLogger(__name__)


def _create_bot() -> Bot:
    """Создаёт экземпляр бота с HTML parse_mode."""
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан")
    return Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def _create_dispatcher() -> Dispatcher:
    """Создаёт диспетчер с in-memory хранилищем FSM."""
    return Dispatcher(storage=MemoryStorage())


async def main() -> None:
    """Настраивает логирование, регистрирует хендлеры и запускает polling."""
    bot = _create_bot()
    dp = _create_dispatcher()

    setup_logger(bot)
    logger.info("Регистрация обработчиков...")
    register_handlers(dp)

    logger.info("Удаление старых апдейтов и запуск polling...")
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        logger.info("Bot started (polling mode).")
        await dp.start_polling(bot)
    except asyncio.CancelledError:  # нормальное завершение
        logger.info("Polling cancelled.")
        raise
    finally:
        # Явно закрываем сессию бота
        await bot.session.close()
        logger.info("Bot session closed.")


if __name__ == "__main__":  # pragma: no cover
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
    except Exception:  # noqa: BLE001
        logger.exception("Критическая ошибка при запуске")
