from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiosend import CryptoPay, TESTNET

from config import BOT_TOKEN, CMC_API_KEY


bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))

dp = Dispatcher(storage=MemoryStorage())
crypto_pay = CryptoPay(token=CMC_API_KEY)