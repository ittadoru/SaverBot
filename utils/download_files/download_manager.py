import logging
from aiogram.fsm.context import FSMContext
from aiogram import types

from services.youtube import YTDLPDownloader
from services import get_downloader
from utils.download_files.video_utils import get_video_resolution
from utils.download_files.send import send_video, send_audio
from db.base import get_session
from db.subscribers import is_subscriber
from db.downloads import add_download_link, get_daily_downloads, increment_daily_download, get_or_create_total_download
from db.users import log_user_activity, add_or_update_user
from db.channels import is_channel_guard_enabled, get_required_active_channels
from db.platforms import increment_platform_download
from handlers.user.referral import get_referral_stats
from config import DAILY_DOWNLOAD_LIMITS, SUBSCRIBER_DAILY_LIMIT
from utils.get_file_max_mb import get_max_filesize_mb

logger = logging.getLogger(__name__)
BUSY_KEY = "busy"


# ---------------- Busy-state ----------------
async def is_busy(state: FSMContext) -> bool:
    data = await state.get_data()
    return data.get(BUSY_KEY, False)


async def set_busy(state: FSMContext, value: bool):
    await state.update_data({BUSY_KEY: value})


# ---------------- Лимиты и проверки ----------------
async def check_download_permissions(user_id: int):
    """
    Проверка: дневные лимиты, подписка, обязательные каналы.
    Возвращает (bool, message).
    """
    async with get_session() as session:
        daily = await get_daily_downloads(session, user_id)
        sub = await is_subscriber(session, user_id)
        _, level, is_vip = await get_referral_stats(session, user_id)
        guard_on = await is_channel_guard_enabled(session)
        required_channels = await get_required_active_channels(session) if guard_on and not is_vip else []

    if sub:
        limit = SUBSCRIBER_DAILY_LIMIT
    else:
        limit = DAILY_DOWNLOAD_LIMITS.get(level)

    if limit is not None and daily >= limit:
        return False, f"⚠️ Лимит {limit} скачиваний в день."

    # Проверка подписки на каналы
    if required_channels:
        # тут нет объекта message, поэтому просто вернём текст
        lines = ["<b>Для скачивания необходимо подписаться на каналы:</b>\n"]
        for ch in required_channels:
            lines.append(f"👉 <a href='https://t.me/{ch.username}'>@{ch.username}</a>")
        lines.append("\nПосле подписки отправьте ссылку ещё раз.")
        return False, "\n".join(lines)

    return True, ""

# ---------------- Скачивание ----------------
async def process_youtube_or_other(
    message: types.Message,
    url: str,
    user_id: int,
    platform: str,
    state: FSMContext,
    mode: str | int = None,
):
    """Скачивает видео или аудио с учетом лимитов и статусов пользователя."""
    try:
        if platform == "youtube":
            downloader = YTDLPDownloader()
            async with get_session() as session:
                _, level, _ = await get_referral_stats(session, user_id)
                sub = await is_subscriber(session, user_id)

            max_filesize_mb = await get_max_filesize_mb(level, sub)

            if mode == "audio":
                file_path = await downloader.download_audio(url)
                if not file_path:
                    logger.warning("[DOWNLOAD] downloader returned empty result for audio: %s", url)
                    return await message.answer("❗️ Не удалось скачать аудио: контент недоступен или требуется вход.")
                await send_audio(message.bot, message, message.chat.id, file_path)

            elif mode and str(mode).isdigit():
                result = await downloader.download_by_itag(url, int(mode), message, user_id)
                if isinstance(result, tuple) and result[0] == "DENIED_SIZE":
                    return await message.answer(
                        f"⚠️ Видео слишком большое: {result[1]} МБ. "
                        f"Ваш лимит — {max_filesize_mb} МБ."
                    )
                if result is None:
                    logger.warning("[DOWNLOAD] downloader returned None for itag download: %s", url)
                    return await message.answer("❗️ Не удалось скачать: контент недоступен или требуется вход.")
                if isinstance(result, tuple):
                    logger.warning("[DOWNLOAD] downloader returned error tuple for itag: %s -> %s", url, result)
                    return await message.answer(f"❗️ Ошибка при скачивании: {result}")
                file_path = result
                w, h = get_video_resolution(file_path)
                await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)

            else:
                result = await downloader.download(url, message, user_id)
                if isinstance(result, tuple) and result[0] == "DENIED_SIZE":
                    return await message.answer(
                        f"⚠️ Видео слишком большое: {result[1]} МБ. "
                        f"Ваш лимит — {max_filesize_mb} МБ."
                    )
                if result is None:
                    logger.warning("[DOWNLOAD] downloader returned None for download: %s", url)
                    return await message.answer("❗️ Не удалось скачать: контент недоступен или требуется вход.")
                if isinstance(result, tuple):
                    logger.warning("[DOWNLOAD] downloader returned error tuple: %s -> %s", url, result)
                    return await message.answer(f"❗️ Ошибка при скачивании: {result}")
                file_path = result
                w, h = get_video_resolution(file_path)
                await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)

        else:
            downloader = get_downloader(url)
            result = await downloader.download(url, user_id)
            if result is None:
                logger.warning("[DOWNLOAD] downloader returned None for non-youtube: %s", url)
                return await message.answer("❗️ Не удалось скачать: контент недоступен или требуется вход.")
            if isinstance(result, tuple):
                logger.warning("[DOWNLOAD] downloader returned error tuple for non-youtube: %s -> %s", url, result)
                return await message.answer(f"❗️ Ошибка при скачивании: {result}")
            file_path = result
            w, h = get_video_resolution(file_path)
            await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)

        # логируем действия
        async with get_session() as session:
            await add_or_update_user(
                session,
                user_id,
                getattr(message.from_user, "first_name", None),
                getattr(message.from_user, "username", None),
            )
            await log_user_activity(session, user_id)
            await increment_daily_download(session, user_id)
            total_row = await get_or_create_total_download(session, user_id)
            total_row.total += 1
            await add_download_link(session, user_id, url)
            await increment_platform_download(session, user_id, platform)
            await session.commit()

    except Exception as e:
        logger.error(f"❌ [DOWNLOAD] Ошибка при скачивании: {e}", exc_info=True)
        await message.answer("❗️ Ошибка при скачивании, попробуйте позже.")
    finally:
        await set_busy(state, False)
