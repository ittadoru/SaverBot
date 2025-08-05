import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Токен бота
ADMINS = list(map(int, os.getenv("ADMINS", "").split(",")))  # Админы по ID
ADMIN_ERROR = int(os.getenv("ADMIN"))  # Админ для ошибок
USE_PYTUBE = os.getenv("USE_PYTUBE", "False").lower() == "true"  # Использовать pytube
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")  # Подключение к Redis
SUPPORT_GROUP_ID = int(os.getenv("SUPPORT_GROUP_ID"))  # ID группы поддержки
SHOP_ID = int(os.getenv("SHOP_ID"))  # ID магазина
API_KEY = os.getenv("API_KEY")  # API ключ для магазина
DOMAIN = os.getenv("DOMAIN") # Домен

DOWNLOAD_DIR = "downloads"  # Папка для загрузок
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)  # Создаем папку для загрузок, если не существует