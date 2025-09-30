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


DAILY_DOWNLOAD_LIMITS = {
    1: 10,
    2: 15,
    3: 20,
    4: 35,
    5: 50,
}
SUBSCRIBER_DAILY_LIMIT = 50
DOWNLOAD_FILE_LIMIT = 100

FORMAT_SELECTION_TIMEOUT = 60

SUBSCRIPTION_YEARS_FOR_LIFETIME = 100
SUBSCRIPTION_LIFETIME_DAYS = SUBSCRIPTION_YEARS_FOR_LIFETIME * 365

BROADCAST_PROGRESS_UPDATE_INTERVAL = 7
BROADCAST_PER_MESSAGE_DELAY = 0.2

REF_GIFT_DAYS = 3


os.makedirs(DOWNLOAD_DIR, exist_ok=True)

