"""Логирование: ротация файлов, цветная консоль и отправка ошибок в Telegram."""

import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler

from aiogram import Bot
from colorlog import ColoredFormatter

from config import PRIMARY_ADMIN_ID


class TelegramErrorHandler(logging.Handler):
    """Кастомный обработчик для отправки критических логов в Telegram."""

    def __init__(self, bot: Bot, level=logging.ERROR):
        super().__init__(level=level)
        self.bot = bot
        self.last_sent_time = 0
        self.cooldown = 60  # seconds

    def emit(self, record: logging.LogRecord):
        """Отправляет отформатированную запись лога в Telegram."""
        current_time = time.time()
        if current_time - self.last_sent_time < self.cooldown:
            return  # Не отправляем, если не прошел кулдаун

        log_entry = self.format(record)
        # Экранируем HTML-символы
        log_entry = log_entry.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if len(log_entry) > 4000:
            log_entry = log_entry[:4000] + "\n... (сообщение обрезано)"

        try:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self.bot.send_message(
                        chat_id=PRIMARY_ADMIN_ID,
                        text=f"🆘 <b>Обнаружена ошибка:</b>\n\n<pre>{log_entry}</pre>",
                        parse_mode="HTML"
                    )
                )
                self.last_sent_time = current_time
            except RuntimeError:
                logging.getLogger(__name__).warning(
                    "Не удалось отправить лог в Telegram: event loop не запущен."
                )
        except Exception as e:
            logging.getLogger(__name__).exception(
                f"Не удалось отправить лог ошибки в Telegram: {e}"
            )

class YTDlpLoggerAdapter:
    """Минимальный адаптер: убран вывод прогресса и процентов.

    Только пробрасывает info/warning/error. debug подавляется, чтобы не засорять логи.
    Если понадобится вернуть прогресс — его можно восстановить из git истории.
    """
    def __init__(self):
        self._logger = get_logger("yt_dlp")

    def info(self, msg):
        return
    
    def warning(self, msg):
        return

    def error(self, msg):
        self._logger.error("[YTDLP] %s", msg)

    def debug(self, msg):
        return
    
def custom_rotator(source, dest):
    """Переименовывает архивные логи в формат bot_YYYY-MM-DD.log."""
    dirname, basename = os.path.split(dest)
    date_part = basename.split('.')[-1]
    new_name = os.path.join(dirname, f"bot_{date_part}.log")
    if os.path.exists(new_name):
        os.remove(new_name)
    os.rename(source, new_name)


def setup_logger(bot: Bot = None):
    """
    Настраивает корневой логгер для всего приложения.
    - Пишет DEBUG логи в файл с ротацией.
    - Пишет INFO логи в консоль с цветовым выделением.
    - Отправляет ERROR логи в Telegram, если передан bot.
    - Фильтрует "шумные" логи от сторонних библиотек.
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # --- Форматтеры ---
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )

    # --- Обработчик для файла (с ротацией) ---
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "bot.log"),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    file_handler.rotator = custom_rotator

    # --- Обработчик для консоли ---
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    # --- Получаем корневой логгер и настраиваем его ---
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # --- Обработчик для Telegram (если передан бот) ---
    if bot:
        error_formatter = logging.Formatter(
            "%(levelname)s | %(name)s:%(lineno)d\n\n%(message)s"
        )
        telegram_handler = TelegramErrorHandler(bot=bot)
        telegram_handler.setFormatter(error_formatter)
        root_logger.addHandler(telegram_handler)

    # --- Фильтрация логов сторонних библиотек ---
    # Значение по умолчанию: показывать только WARNING и выше.
    # Теперь ужесточим SQLAlchemy до ERROR, чтобы скрыть INFO/DEBUG (в т.ч. SQL) при echo=False.
    sql_level_name = os.getenv("SQLALCHEMY_LOG_LEVEL", "ERROR").upper()
    valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    if sql_level_name not in valid_levels:
        sql_level_name = "ERROR"
    sql_level = getattr(logging, sql_level_name, logging.ERROR)

    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(sql_level)
    logging.getLogger("sqlalchemy.pool").setLevel(sql_level)
    logging.getLogger("sqlalchemy.dialects").setLevel(sql_level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.info("Система логирования успешно настроена. (SQLALCHEMY_LOG_LEVEL=%s, echo=%s)", sql_level_name, os.getenv("SQL_ECHO"))


_LOG_MESSAGE_WARNED = False


def log_message(message: str, level: int = 0, emoji: str = "", log_level: str = "info"):
    """DEPRECATED: Используйте стандартный logger.{info,warning,error,debug}. Останется для совместимости.

    Параметры:
        message: текст.
        level: индентация (legacy) — преобразуется в пробелы * 3.
        emoji: добавляется префиксом.
        log_level: какой метод вызвать.
    """
    global _LOG_MESSAGE_WARNED  # noqa: PLW0603
    if not _LOG_MESSAGE_WARNED:
        logging.getLogger(__name__).warning(
            "log_message() устарел — переходите на стандартный logger.* (выводится один раз)"
        )
        _LOG_MESSAGE_WARNED = True

    indent = " " * (level * 3)
    prefix = f"{emoji} " if emoji else ""
    full_message = f"{indent}{prefix}{message}"
    logger = logging.getLogger(__name__)
    lvl = log_level.lower()
    if lvl == "info":
        logger.info(full_message)
    elif lvl == "warning":
        logger.warning(full_message)
    elif lvl == "error":
        logger.error(full_message)
    elif lvl == "debug":
        logger.debug(full_message)
    else:
        logger.info(full_message)


def log_error(error: Exception, context: str = ""):
    """
    Логирует исключение с полным traceback.
    """
    logger = logging.getLogger()
    error_message = f"Произошла ошибка: {context}" if context else "Произошла ошибка"
    logger.error(error_message, exc_info=error)


class ContextLoggerAdapter(logging.LoggerAdapter):
    """Адаптер для добавления контекста (user_id, url, platform и т.п.).

    Пример:
        logger = get_logger(__name__, user_id=123)
        logger.info("Начало загрузки", extra={'url': url})
    """

    def process(self, msg, kwargs):  # noqa: D401
        if 'extra' in kwargs:
            # Сливаем наш контекст и переданный
            merged = {**self.extra, **kwargs['extra']}
        else:
            merged = self.extra
        ctx_str = " ".join(f"{k}={v}" for k, v in merged.items() if v is not None)
        if ctx_str:
            msg = f"{msg} | {ctx_str}"
        return msg, kwargs


def get_logger(name: str, **context) -> logging.Logger:
    """Возвращает адаптированный логгер с контекстом.

    Если контекст не нужен — можно просто вызвать get_logger(__name__).
    """
    base = logging.getLogger(name)
    if context:
        return ContextLoggerAdapter(base, context)  # type: ignore[return-value]
    return base
