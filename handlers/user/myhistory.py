from aiogram import Router
from aiogram.types import CallbackQuery
from db.base import get_session
from db.downloads import get_last_links
from utils.keyboards import back_button
from datetime import timezone, timedelta


router = Router()


@router.callback_query(lambda c: c.data == "download_history")
async def show_download_history(callback: CallbackQuery):
    """Показывает последние 10 скачиваний пользователя (кликабельные ссылки).

    Время локализовано в московский часовой пояс (MSK, UTC+3).
    Без дополнительных кнопок — пользователи кликают по ссылке в тексте.
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
    lines = []
    for idx, (url, created_at) in enumerate(links, start=1):
        # Ensure created_at has tzinfo; DB stores UTC (naive datetime), treat as UTC
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_msk = created_at.astimezone(msk)
        time_str = created_msk.strftime('%d.%m.%Y %H:%M') + ' MSK'
        preview = url if len(url) <= 60 else url[:57] + '...'
        # Make clickable link using HTML
        lines.append(f"<b>{idx}.</b> <a href=\"{url}\">{preview}</a> — <code>{time_str}</code>")

    text = "<b>🕓 Последние скачивания (последние 10):</b>\n\n" + "\n".join(lines)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_button("start"))
    await callback.answer()
