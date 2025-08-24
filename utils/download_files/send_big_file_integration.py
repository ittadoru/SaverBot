import subprocess
import sys
import logging

logger = logging.getLogger(__name__)

async def send_big_file_telethon(chat_id: str, file_path: str, caption: str = None):
    """
    Вызывает внешний скрипт send_big_file.py для отправки больших файлов через Telethon.
    chat_id: username (с @) или числовой id
    file_path: путь к файлу
    caption: подпись (опционально)
    """
    cmd = [sys.executable, 'utils/download_files/send_big_file.py', chat_id, file_path]
    if caption:
        cmd.append(caption)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Telethon send_big_file.py error: {result.stderr}")
        else:
            logger.info(f"Telethon send_big_file.py output: {result.stdout}")
    except Exception as e:
        logger.error(f"Ошибка при вызове send_big_file.py: {e}")
