from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
import asyncio

from config import BOT_TOKEN
from handlers import register_handlers
from aiogram.client.bot import DefaultBotProperties
import logging

logging.basicConfig(
    level=logging.INFO,  # можно DEBUG для отладки
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

def main():
    register_handlers(dp)
    asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    main()
