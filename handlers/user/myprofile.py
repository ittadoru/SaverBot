
from aiogram import Router, F, types
from aiogram.types import CallbackQuery
from datetime import datetime
from utils.redis import r, get_platform_stats, get_user_links

router = Router()

@router.callback_query(lambda c: c.data == "myprofile")
async def show_profile(callback: CallbackQuery):
    """Обработка введённого ID или username, поиск истории ссылок пользователя."""
    user_id = callback.from_user.id

    # Если пользователь не найден
    if user_id is None:
        await callback.message.answer("❌ Пользователь не найден.")
        return

    # Получение информации о пользователе
    expire_timestamp = await r.get(f"subscriber:expire:{user_id}")
    if expire_timestamp:
        expire_timestamp = int(expire_timestamp)
        expiry_date = datetime.fromtimestamp(expire_timestamp)
        if expiry_date > datetime.now():
            subscription_status = f"✅ Подписка активна до <b>{expiry_date.strftime('%d.%m.%Y %H:%M')}</b>"
        else:
            subscription_status = "❌ Подписка истекла"
    else:
        subscription_status = "❌ Подписка не активна"

    name = callback.from_user.first_name or "Без имени"
    username = callback.from_user.username or ""

    user_info = "<b>👤 Пользователь:</b>\n\n"
    user_info += f"ID: <code>{user_id}</code>\n"
    user_info += f"Имя: {name}\n"
    user_info += f"{subscription_status}\n"
    user_info += f"Username: @{username}\n"

    # Статистика по платформам
    platform_stats = await get_platform_stats(user_id)
    if platform_stats:
        sorted_stats = sorted(platform_stats.items(), key=lambda x: x[1], reverse=True)
        stats_text = "\n".join([f"{platform}: {count}" for platform, count in sorted_stats])
        stats_block = f"\n\n<b>Статистика по платформам:</b>\n<pre>{stats_text}</pre>"
    else:
        stats_block = "\n\n<b>Статистика по платформам:</b>\nНет скачиваний."

    # Последние 5 ссылок
    links = await get_user_links(user_id)
    if links:
        links_text = "\n".join([f"<pre>{link}</pre>" for link in links[:5]])
        links_block = f"\n\n<b>Последние 5 ссылок:</b>\n{links_text}"
    else:
        links_block = "\n\n<b>Последние 5 ссылок:</b>\nНет недавних ссылок."

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
        ]
    )

    full_text = user_info + stats_block + links_block
    await callback.message.edit_text(full_text, parse_mode="HTML", reply_markup=keyboard)
