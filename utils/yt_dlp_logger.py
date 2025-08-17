from utils.logger import get_logger

_logger = get_logger("yt_dlp")


class YTDlpLoggerAdapter:
    """Минимальный адаптер: убран вывод прогресса и процентов.

    Только пробрасывает info/warning/error. debug подавляется, чтобы не засорять логи.
    Если понадобится вернуть прогресс — его можно восстановить из git истории.
    """

    def info(self, msg):  # noqa: D401
        _logger.info("[YTDLP] %s", msg)

    def warning(self, msg):  # noqa: D401
        _logger.warning("[YTDLP] %s", msg)

    def error(self, msg):  # noqa: D401
        _logger.error("[YTDLP] %s", msg)

    def debug(self, msg):  # noqa: D401
        # Полностью игнорируем отладочные/прогресс строки
        return
