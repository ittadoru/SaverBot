"""Точка входа: инициализация логирования, создание бота/DP и запуск polling."""

from __future__ import annotations

import asyncio
import logging
from aiogram import Bot
from aiogram.types import BotCommand

from loader import bot, dp
from handlers import register_handlers
from utils.logger import setup_logger

logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Устанавливает команды для меню бота."""
    commands = [
        BotCommand(command="subscribe", description="⭐️ Оформить подписку"),
        BotCommand(command="start", description="👤 Профиль"),
        BotCommand(command="invite", description="👥 Пригласить друга"),
        BotCommand(command='help', description='❓ Обратиться в поддержку'),
        BotCommand(command="promocode", description="🎁 Активировать промокод"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    """Настраивает логирование, регистрирует хендлеры и запускает polling."""

    setup_logger(bot)
    logger.info("Регистрация обработчиков...")
    register_handlers(dp)

    logger.info("Установка команд бота...")
    await set_bot_commands(bot)

    logger.info("Удаление старых апдейтов и запуск polling...")
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        logger.info("Bot started (polling mode).")
        await dp.start_polling(bot)
    except asyncio.CancelledError:  # нормальное завершение
        logger.info("Polling cancelled.")
        raise
    finally:
        await bot.session.close()
        logger.info("Bot session closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
    except Exception:
        logger.exception("Критическая ошибка при запуске")
