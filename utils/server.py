import asyncio
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from utils import logger as log


app = FastAPI()

@app.get("/video/{filename}")
async def download_video(filename: str):
    filepath = f"downloads/{filename}"

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="video/mp4"
    )

async def remove_file_later(path: str, delay: int):
    log.log_message(f"[CLEANUP] Планируется удаление через {delay} секунд: {path}", emoji="⏳",)
    await asyncio.sleep(delay)
    try:
        os.remove(path)
        log.log_cleanup_video(path)
    except FileNotFoundError:
        log.log_message(f"⚠️ Файл не найден для удаления: {path}", level=1)
