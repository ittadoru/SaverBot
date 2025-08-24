from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from services.youtube import YTDLPDownloader
from .download_manager import get_max_filesize_mb


async def prepare_youtube_menu(url: str, user_id: int):
    """
    Возвращает (keyboard, caption, preview) для выбора качества YouTube-видео.
    """
    downloader = YTDLPDownloader()
    info = await downloader.get_available_video_options(url)

    preview = info["thumbnail_url"]

    # получаем доступные форматы
    unique_res = {}
    for fmt in info["formats"]:
        if fmt.get("mime_type") == "video/mp4":
            res_str = fmt.get("res")
            if res_str and res_str.endswith("p"):
                try:
                    res_int = int(res_str.replace("p", ""))
                    if 240 <= res_int <= 1080:
                        if (
                            res_str not in unique_res
                            or (fmt.get("progressive") and not unique_res[res_str].get("progressive"))
                        ):
                            unique_res[res_str] = fmt
                except (ValueError, TypeError):
                    continue

    sorted_res = sorted(unique_res.items(), key=lambda x: int(x[0].replace("p", "")))
    max_res = max([int(r.replace("p", "")) for r, _ in sorted_res], default=0)

    # текст
    lines = [f"<b>🎬 {info['title']}</b>\n", "Приблизительные размеры:"]
    rows = []
    row = []

    for res, fmt in sorted_res:
        size_mb = fmt.get("size_mb") or (fmt.get("filesize", 0) / 1024 / 1024)
        size_str = f"{size_mb:.0f}MB" if size_mb else "?MB"

        emoji = "⚡️"
        cb = f"ytres:{fmt['itag']}"

        row.append(InlineKeyboardButton(text=f"{emoji} {res}", callback_data=cb))
        if len(row) == 2:
            rows.append(row)
            row = []

        lines.append(f"{emoji}  {res}: {size_str}")

    if row:
        rows.append(row)

    # аудио
    rows.append([InlineKeyboardButton(text="🎧 Аудио", callback_data=f"ytdl:audio:{url}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    lines.append("\n<i>Выберите разрешение или получите только аудио:</i>")

    return keyboard, "\n".join(lines), preview
