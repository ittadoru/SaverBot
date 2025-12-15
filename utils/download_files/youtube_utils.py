from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from services.youtube import YTDLPDownloader


async def prepare_youtube_menu(url: str, user_id: int):
    """
    Возвращает (keyboard, caption, preview) для выбора качества YouTube-видео.
    """
    downloader = YTDLPDownloader()
    info = await downloader.get_available_video_options(url)
    preview = info["thumbnail_url"]

    # Получаем статус пользователя
    from db.base import get_session
    from db.subscribers import is_subscriber as db_is_subscriber
    from handlers.user.referral import get_referral_stats
    async with get_session() as session:
        sub = await db_is_subscriber(session, user_id)
        _, level, _ = await get_referral_stats(session, user_id)

    # Фильтрация форматов по статусу
    from config import DOWNLOAD_FILE_LIMIT
    def is_format_allowed(fmt):
        res_int = int(fmt["res"].replace("p", ""))
        size_mb = fmt["size_mb"]
        if sub:
            return 240 <= res_int <= 1080 and size_mb <= DOWNLOAD_FILE_LIMIT * 10
        if level == 2:
            return res_int < 720 and size_mb <= DOWNLOAD_FILE_LIMIT * 2
        if level == 3:
            return res_int < 720 and size_mb <= DOWNLOAD_FILE_LIMIT * 4
        if level == 4:
            return res_int < 720 and size_mb <= DOWNLOAD_FILE_LIMIT * 10
        return res_int < 720 and size_mb <= DOWNLOAD_FILE_LIMIT


    # Собираем все уникальные разрешения
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

    # текст
    lines = [f"<b>🎬 {info['title']}</b>\n", "Приблизительные размеры:"]
    rows = []
    row = []

    for res, fmt in sorted_res:
        size_mb = fmt.get("size_mb") or (fmt.get("filesize", 0) / 1024 / 1024)
        size_str = f"{size_mb:.0f}MB" if size_mb else "?MB"
        allowed = is_format_allowed(fmt)
        emoji = "⚡️" if allowed else "🔒"
        cb = f"ytres:{fmt['itag']}" if allowed else "disabled"
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
