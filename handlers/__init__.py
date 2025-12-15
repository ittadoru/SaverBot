from aiogram import Dispatcher

from .user import routers as user_routers  # Роутеры для пользовательских команд
from .admin import routers as admin_routers  # Роутеры для админских команд
from .support import routers as support_routers  # Роутер поддержки

def register_handlers(dp: Dispatcher):
    # Регистрируем роутеры админов
    for router in admin_routers:
        dp.include_router(router)

    # Регистрируем роутеры пользователей
    for router in user_routers:
        dp.include_router(router)

    # Регистрируем роутеры поддержки
    for router in support_routers:
        dp.include_router(router)
