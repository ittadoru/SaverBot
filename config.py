# config.py
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = list(map(int, os.getenv("ADMINS", "").split(",")))
USE_PYTUBE = os.getenv("USE_PYTUBE", "False").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Папка для временного хранения видео
DOWNLOAD_DIR = "downloads"