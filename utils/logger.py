import logging
import traceback
import colorlog
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

# Создаем папку logs, если ее нет
os.makedirs("logs", exist_ok=True)

# === Цветной логгер для консоли ===
console_handler = colorlog.StreamHandler()
console_formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
    },
)
console_handler.setFormatter(console_formatter)

# === Ротация файла раз в сутки ===
file_handler = TimedRotatingFileHandler(
    filename="logs/bot.log",
    when="midnight",
    interval=1,
    backupCount=30,           # Сколько логов хранить
    encoding="utf-8",
    utc=False
)

# Формат логов для файлов
file_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

# === Кастомный постфикс для файлов ===
# Пример: bot_2025-08-02.log
file_handler.namer = lambda name: name.replace("bot.log", f"bot_{datetime.now().date()}.log")

# === Общий логгер ===
logger = colorlog.getLogger("SaveBotLogger")
logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_message(message: str, level: int = 0, emoji: str = "", log_level: str = "info"):
    """
    Основная функция логирования с поддержкой отступов и эмодзи.
    level — уровень вложенности для отступа, emoji — добавляет визуальный акцент.
    """
    indent = " " * (level * 3)
    prefix = f"{emoji} " if emoji else ""
    full_message = f"{indent}{prefix}{message}"

    if log_level == "info":
        logger.info(full_message)
    elif log_level == "warning":
        logger.warning(full_message)
    elif log_level == "error":
        logger.error(full_message)
    else:
        logger.debug(full_message)


def log_receive(user_username: str, user_id: int):
    """Логируем получение URL от пользователя"""
    log_message("[RECEIVE] Получен URL", emoji="🌐")
    log_message(f"От пользователя: @{user_username} (id={user_id})", level=1)


def log_download_start(url: str):
    """Логируем старт скачивания видео"""
    log_message("[DOWNLOAD] Старт загрузки с YouTube", emoji="⏬")
    log_message(f"URL: {url}", level=1)


def log_download_complete(file_path: str):
    """Логируем успешное завершение скачивания"""
    log_message("[DOWNLOAD] Видео скачано", emoji="✅")
    log_message(f"Файл: {file_path}", level=1)


def log_send_start(chat_id: int):
    """Логируем начало отправки видео в Telegram"""
    log_message("[SEND] Отправка в Telegram", emoji="✉️")
    log_message(f"Чат: {chat_id}", level=1)


def log_send_complete():
    """Логируем успешную отправку видео"""
    log_message("[SEND] Отправка завершена", emoji="✅")


def log_user_sent(user_username: str, user_id: int):
    """Логируем факт отправки видео конкретному пользователю"""
    log_message("[USER] Видео отправлено пользователю", emoji="👤")
    log_message(f"@{user_username} (id={user_id})", level=1)


def log_cleanup_video(file_path: str):
    """Логируем удаление видеофайла после отправки"""
    log_message("[CLEANUP] Видео удалено", emoji="🗑")
    log_message(f"Файл: {file_path}", level=1)


def log_error(error: Exception, username: str, context: str = ""):
    """
    Логирует исключение с полным трассировкой (traceback).
    Позволяет указать контекст ошибки и пользователя, при котором она произошла.
    """
    log_message(f"[ERROR] Произошла ошибка (@{username})", emoji="❌", log_level="error")
    if context:
        log_message(f"Контекст: {context}", level=1, log_level="error")
    tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    log_message(tb, level=1, log_level="error")
