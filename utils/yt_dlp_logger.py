import sys
import re
from utils import logger as log


class YTDlpLoggerAdapter:
    """
    Адаптер логгера для yt-dlp, который перенаправляет сообщения в кастомный логгер.
    Отслеживает прогресс загрузки и отображает его в консоли в виде прогресс-бара.
    """

    def __init__(self):
        self.last_percent = None
        self.total_files = 2  
        self.downloaded_files = 0  

    def info(self, msg):
        """Логирование информационных сообщений."""
        log.log_message(f"[YTDLP] {msg}", log_level="info")

    def warning(self, msg):
        """Логирование предупреждений."""
        log.log_message(f"[YTDLP] {msg}", log_level="warning")

    def error(self, msg):
        """Логирование ошибок."""
        log.log_message(f"[YTDLP] {msg}", log_level="error")

    def debug(self, msg):
        """
        Обработка отладочных сообщений.
        Отслеживает сообщения с прогрессом загрузки и вызывает отображение прогресса.
        """
        if "[download]" in msg and "%" in msg:
            self._print_progress(msg)

    def _print_progress(self, msg):
        """
        Извлекает процент загрузки из сообщения и отображает прогресс-бар в консоли.
        Обновляет количество скачанных файлов, если прогресс достиг 100%.
        """
        match = re.search(r"(\d{1,3}\.\d+)%", msg)
        if not match:
            return

        percent = float(match.group(1))

        # Если прогресс достиг 100%, увеличиваем счетчик скачанных файлов
        if percent >= 100 and (self.last_percent is None or self.last_percent < 100):
            self.downloaded_files = min(self.downloaded_files + 1, self.total_files)

        # Обновляем прогресс, если разница с предыдущим >= 1%
        if self.last_percent is None or abs(percent - self.last_percent) >= 1:
            self.last_percent = percent
            current_file_num = min(self.downloaded_files + 1, self.total_files)
            bar = self._make_bar(percent)
            status = f"{current_file_num} из {self.total_files} скачивается"

            # Перенос строки при завершении последнего файла, иначе возврат каретки
            end = "\n" if percent >= 100 and self.downloaded_files == self.total_files else "\r"
            sys.stdout.write(f"\r{status}: {bar} {percent:.1f}%{end}")
            sys.stdout.flush()

    def _make_bar(self, percent):
        """
        Создает строку с прогресс-баром длиной 20 блоков.
        Заполняет блоки согласно проценту загрузки.
        """
        total_blocks = 20
        filled = int(percent / 100 * total_blocks)
        return f"[{'█' * filled}{'░' * (total_blocks - filled)}]"
