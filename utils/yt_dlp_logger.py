import sys
import re
from utils import logger as log


class YTDlpLoggerAdapter:
    def info(self, msg):
        log.log_message(f"[YTDLP] {msg}", log_level="info")

    def warning(self, msg):
        log.log_message(f"[YTDLP] {msg}", log_level="warning")

    def error(self, msg):
        log.log_message(f"[YTDLP] {msg}", log_level="error")

    def __init__(self):
        self.last_percent = None
        self.total_files = 2
        self.downloaded_files = 0

    def debug(self, msg):
        if "[download]" in msg and "%" in msg:
            self._print_progress(msg)

    def _print_progress(self, msg):
        match = re.search(r"(\d{1,3}\.\d+)%", msg)
        if not match:
            return

        percent = float(match.group(1))

        if percent >= 100 and (self.last_percent is None or self.last_percent < 100):
            self.downloaded_files = min(self.downloaded_files + 1, self.total_files)

        if self.last_percent is None or abs(percent - self.last_percent) >= 1:
            self.last_percent = percent
            current_file_num = min(self.downloaded_files + 1, self.total_files)
            bar = self._make_bar(percent)
            status = f"{current_file_num} из {self.total_files} скачивается"
        
            end = "\n" if percent >= 100 and self.downloaded_files == self.total_files else "\r"
            sys.stdout.write(f"\r{status}: {bar} {percent:.1f}%{end}")
            sys.stdout.flush()


    def _make_bar(self, percent):
        total_blocks = 20
        filled = int(percent / 100 * total_blocks)
        return f"[{'█' * filled}{'░' * (total_blocks - filled)}]"
