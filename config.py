import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMINS = list(map(int, os.getenv("ADMINS", "").split(",")))

DATABASE_URL = os.getenv("DATABASE_URL")

SUPPORT_GROUP_ID = int(os.getenv("SUPPORT_GROUP_ID"))
SUBSCRIBE_TOPIC_ID = int(os.getenv("SUBSCRIBE_TOPIC_ID"))
NEW_USER_TOPIC_ID = int(os.getenv("NEW_USER_TOPIC_ID"))

SHOP_ID = int(os.getenv("SHOP_ID"))
API_KEY = os.getenv("API_KEY")

DOMAIN = os.getenv("DOMAIN")

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

CMC_API_KEY = os.getenv("CMC_API_KEY")
RUB_PER_USDT = 90.0

# ---------------- Token economy ----------------
DAILY_FREE_TOKENS = 100
WELCOME_BONUS_TOKEN_X = 50
REFERRAL_BONUS_TOKENS = 50
REFERRAL_BONUS_TOKEN_X = 1
TOKEN_X_TO_TOKEN_RATE = 15

SOCIAL_DAILY_LIMIT = 20
SOCIAL_RESET_TOKEN_COST = 100
SOCIAL_RESET_TOKEN_X_COST = 2

YOUTUBE_MAX_DURATION_SECONDS = 3 * 60 * 60
YOUTUBE_DURATION_BUCKETS_SECONDS = (
    5 * 60,   # < 5 min
    30 * 60,  # < 30 min
    3 * 60 * 60,  # < 3 hours
)
YOUTUBE_PRICING = {
    "480p": {"currency": "token", "tiers": (5, 10, 20)},
    "720p": {"currency": "token", "tiers": (7, 15, 27)},
    "1080p": {"currency": "token", "tiers": (10, 20, 35)},
    "1440p": {"currency": "token_x", "tiers": (1, 3, 7)},
    "4k": {"currency": "token_x", "tiers": (2, 7, 15)},
    "audio": {"currency": "token", "tiers": (2, 5, 10)},
}


DOWNLOAD_FILE_LIMIT = 100

BROADCAST_PROGRESS_UPDATE_INTERVAL = 7
BROADCAST_PER_MESSAGE_DELAY = 0.2


os.makedirs(DOWNLOAD_DIR, exist_ok=True)
