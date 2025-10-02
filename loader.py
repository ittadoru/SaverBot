from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiosend import CryptoPay

from config import BOT_TOKEN, CMC_API_KEY


def create_bot() -> Bot:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан")

    # тут указываем локальный API-сервер
    session = AiohttpSession(
        api=TelegramAPIServer.from_base("http://saverbot_tgapi:8081", is_local=True)
    )

    return Bot(
        token=BOT_TOKEN,
        session=session,
        parse_mode=ParseMode.HTML,
    )

dp = Dispatcher(storage=MemoryStorage())
crypto_pay = CryptoPay(token=CMC_API_KEY)