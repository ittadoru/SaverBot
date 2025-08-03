import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = list(map(int, os.getenv("ADMINS", "").split(",")))
ADMIN_ERROR = int(os.getenv("ADMIN"))
USE_PYTUBE = os.getenv("USE_PYTUBE", "False").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SUPPORT_GROUP_ID = int(os.getenv("SUPPORT_GROUP_ID"))

DOWNLOAD_DIR = "downloads"