from aiogram import Router, types, Bot
from aiogram.filters import Command
from utils import redis
import random

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, bot: Bot):
    """
    Обрабатывает команду /start.
    Проверяет, новый ли пользователь, и добавляет его в базу данных.
    Если пользователь новый, генерирует уникальный промокод на 7 дней подписки.
    """
    is_new = not await redis.r.sismember("users", message.from_user.id)
    await redis.add_user(message.from_user, bot)
    username = message.from_user.username or message.from_user.full_name or "пользователь"

    if is_new:
        # Генерируем уникальный промокод для нового пользователя
        promo_code = f"WELCOME-{random.randint(100000, 999999)}"
        await redis.add_promocode(promo_code, duration_days=7)
        promo_text = (
            f"В подарок тебе промокод на 7 дней подписки: <pre>{promo_code}</pre>\n"
            "Активируй его через меню профиля, нажми на команду /profile.\n\n"
        )
    else:
        promo_text = ""

    await message.answer(
        f"👋 Привет, {username}!\n\n"
        "Я помогу скачать видео из YouTube, TikTok или Instagram. Просто пришли мне ссылку!\n\n"
        f"{promo_text}"
        "Твой <b>профиль</b> со статистикой и лимитами всегда доступен через меню по команду /profile.",
        parse_mode="HTML"
    )
