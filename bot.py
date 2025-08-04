from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
import asyncio

from config import BOT_TOKEN
from handlers import register_handlers
from aiogram.client.bot import DefaultBotProperties
import logging


# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,  # Можно поменять на DEBUG для подробной отладки
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# Инициализация бота с HTML-парсингом по умолчанию
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Диспетчер с использованием памяти для хранения состояний FSM
dp = Dispatcher(storage=MemoryStorage())


def main():
    """
    Основная функция для регистрации обработчиков и запуска polling.
    """
    register_handlers(dp)
    asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    main()
