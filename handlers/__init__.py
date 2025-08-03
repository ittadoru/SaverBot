from aiogram import Dispatcher

from .user import routers as user_routers  # Собранные роутеры для пользователя
from .admin import routers as admin_routers  # Собранные роутеры
from .support import routers as support_routers  # Роутер поддержки

def register_handlers(dp: Dispatcher):
    # Подключаем admin роутеры через список
    for router in admin_routers:
        dp.include_router(router)

    for router in user_routers:
        dp.include_router(router)

    for router in support_routers:
        dp.include_router(router)
    
