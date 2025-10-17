from aiogram import Router
from aiogram.types import CallbackQuery
from db.base import get_session
from db.downloads import get_last_links
from utils.keyboards import back_button
from datetime import timezone, timedelta, datetime
import html


router = Router()


def _human_delta(delta_seconds: int) -> str:
    if delta_seconds < 60:
        return "только что"
    minutes = delta_seconds // 60
    if minutes < 60:
        return f"{minutes} мин. назад"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ч. назад"
    days = hours // 24
    if days < 30:
        return f"{days} дн. назад"
    months = days // 30
    if months < 12:
        return f"{months} мес. назад"
    years = months // 12
    return f"{years} г. назад"


@router.callback_query(lambda c: c.data == "download_history")
async def show_download_history(callback: CallbackQuery):
    """Показывает последние 10 скачиваний в формате:

    <ссылка>
    DD.MM.YYYY HH:MM MSK — <относительное время>

    и пустая строка между записями.
    """
    user_id = callback.from_user.id
    async with get_session() as session:
        links = await get_last_links(session, user_id, limit=10, include_time=True)

    if not links:
        text = "У вас пока нет истории скачиваний."
        await callback.message.edit_text(text, reply_markup=back_button("start"))
        await callback.answer()
        return

    msk = timezone(timedelta(hours=3))
    now = datetime.now(timezone.utc).astimezone(msk)
    parts: list[str] = []
    for url, created_at in links:
        # normalize created_at: DB stores naive UTC, treat as UTC if tzinfo is missing
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_msk = created_at.astimezone(msk)
        time_str = created_msk.strftime('%d.%m.%Y %H:%M') + ' MSK'
        delta_seconds = int((now - created_msk).total_seconds())
        rel = _human_delta(delta_seconds)

        # Escape HTML-sensitive characters in URL for safe display
        url_esc = html.escape(url, quote=True)

        parts.append(f"<a href=\"{url_esc}\">{url_esc}</a>\n<code>{time_str} — {rel}</code>\n")

    text = "\n".join(parts)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_button("start"))
    await callback.answer()
