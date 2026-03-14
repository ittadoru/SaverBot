import logging

from aiogram import Bot, types
from aiogram.fsm.context import FSMContext

from services import get_downloader
from services.youtube import YTDLPDownloader
from utils.download_files.send import send_audio, send_video
from utils.download_files.video_utils import get_video_resolution
from utils.token_policy import get_youtube_price
from db.base import get_session
from db.channels import (
    check_user_memberships,
    get_required_active_channels,
    is_channel_guard_enabled,
)
from db.downloads import (
    add_download_link,
    get_or_create_total_download,
    increment_daily_download,
)
from db.platforms import increment_platform_download
from db.tokens import (
    get_daily_social_usage,
    increment_daily_social_usage,
    refund_token_x,
    refund_tokens,
    spend_token_x,
    spend_tokens,
)
from db.users import add_or_update_user, log_user_activity
from config import ADMINS, SOCIAL_DAILY_LIMIT

logger = logging.getLogger(__name__)
BUSY_KEY = "busy"
GENERIC_DOWNLOAD_ERROR_TEXT = "❗️Произошла ошибка. Попробуйте позже."


async def is_busy(state: FSMContext) -> bool:
    data = await state.get_data()
    return data.get(BUSY_KEY, False)


async def set_busy(state: FSMContext, value: bool):
    await state.update_data({BUSY_KEY: value})


async def _send_error(message: types.Message, admin_text: str) -> None:
    user_id = getattr(getattr(message, "from_user", None), "id", None)
    if user_id in ADMINS:
        await message.answer(admin_text)
        return
    await message.answer(GENERIC_DOWNLOAD_ERROR_TEXT)


async def check_download_permissions(user_id: int, platform: str, bot: Bot | None = None):
    """
    Checks mandatory channels and Tiktok/Insta daily limit.
    Returns (can_download, reason_html).
    """
    async with get_session() as session:
        missing_channels = []
        guard_on = await is_channel_guard_enabled(session)
        if guard_on:
            required_channels = await get_required_active_channels(session)
            if required_channels and bot is not None:
                checks = await check_user_memberships(bot, user_id, required_channels)
                missing_channels = [item.channel for item in checks if not item.is_member]
            else:
                missing_channels = required_channels

        social_used = 0
        if platform in {"tiktok", "instagram"}:
            social_used = await get_daily_social_usage(session, user_id)
        await session.commit()

    if missing_channels:
        lines = ["<b>Для скачивания нужно подписаться на каналы:</b>\n"]
        for ch in missing_channels:
            lines.append(f"👉 <a href='https://t.me/{ch.username}'>@{ch.username}</a>")
        lines.append("\nПосле подписки отправь ссылку ещё раз.")
        return False, "\n".join(lines)

    if platform in {"tiktok", "instagram"} and social_used >= SOCIAL_DAILY_LIMIT:
        return (
            False,
            (
                f"⚠️ Достигнут лимит Tiktok/Insta: {SOCIAL_DAILY_LIMIT} в день.\n\n"
                "Открой раздел <b>Токены и лимиты</b> в /start, чтобы сбросить лимит:\n"
                "• за 100 токенов\n"
                "• или за 2 tokenX"
            ),
        )

    return True, ""


async def _charge_youtube(user_id: int, currency: str, amount: int) -> bool:
    async with get_session() as session:
        if currency == "token":
            paid, _ = await spend_tokens(session, user_id, amount)
        elif currency == "token_x":
            paid, _ = await spend_token_x(session, user_id, amount)
        else:
            paid = False
        await session.commit()
    return paid


async def _refund_youtube(user_id: int, currency: str, amount: int) -> None:
    async with get_session() as session:
        if currency == "token":
            await refund_tokens(session, user_id, amount)
        elif currency == "token_x":
            await refund_token_x(session, user_id, amount)
        await session.commit()


async def _log_download(
    message: types.Message,
    user_id: int,
    platform: str,
    source_url: str,
) -> None:
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
        await add_download_link(session, user_id, source_url)
        await increment_platform_download(session, user_id, platform)
        if platform in {"tiktok", "instagram"}:
            await increment_daily_social_usage(session, user_id)
        await session.commit()


async def process_youtube_or_other(
    message: types.Message,
    url: str,
    user_id: int,
    platform: str,
    state: FSMContext,
    mode: str | int | None = None,
):
    """Download and send media according to platform and token rules."""
    try:
        if platform == "youtube":
            data = await state.get_data()
            yt_options: dict = data.get("yt_options", {})
            duration_seconds = int(data.get("yt_duration_seconds") or 0)
            quality = str(mode or "").lower()
            if not quality:
                return await message.answer("❗️Сначала выбери качество YouTube.")

            option = yt_options.get(quality)
            if not option:
                return await message.answer("❗️Этот вариант недоступен для текущего видео.")

            price = get_youtube_price(quality, duration_seconds)
            if not price:
                return await message.answer("❗️Нельзя скачать видео длиннее 3 часов.")

            currency, amount = price
            paid = await _charge_youtube(user_id, currency, amount)
            if not paid:
                token_name = "токенов" if currency == "token" else "tokenX"
                return await message.answer(f"❗️Недостаточно {token_name} для этого качества.")

            downloader = YTDLPDownloader()
            file_path: str | None = None

            try:
                if quality == "audio":
                    file_path = await downloader.download_audio(url)
                    if not file_path:
                        await _refund_youtube(user_id, currency, amount)
                        return await _send_error(message, "❗️Не удалось скачать аудио.")
                    sent = await send_audio(message.bot, message, message.chat.id, file_path)
                    if not sent:
                        await _refund_youtube(user_id, currency, amount)
                        return
                else:
                    itag = option.get("itag")
                    if not isinstance(itag, int):
                        await _refund_youtube(user_id, currency, amount)
                        return await _send_error(message, "❗️Формат недоступен для скачивания.")

                    result = await downloader.download_by_itag(url, itag, message, user_id)
                    if not result or isinstance(result, tuple):
                        await _refund_youtube(user_id, currency, amount)
                        return await _send_error(message, "❗️Не удалось скачать видео.")

                    file_path = result
                    w, h = get_video_resolution(file_path)
                    sent = await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)
                    if not sent:
                        await _refund_youtube(user_id, currency, amount)
                        return
            except Exception:
                await _refund_youtube(user_id, currency, amount)
                raise

            await _log_download(message, user_id, platform, url)
            return

        downloader = get_downloader(url)
        if downloader is None:
            logger.warning("[DOWNLOAD] unsupported platform for url: %s", url)
            return await message.answer("❗️Эта платформа пока не поддерживается.")

        result = await downloader.download(url, message=message, user_id=user_id)
        if result is None:
            logger.warning("[DOWNLOAD] downloader returned None for non-youtube: %s", url)
            if platform == "instagram":
                return await _send_error(
                    message,
                    "❗️Instagram не отдал медиа без авторизации. "
                    "Пост может быть приватным или требовать cookies.",
                )
            return await _send_error(message, "❗️Не удалось скачать: контент недоступен или нужен логин.")

        if isinstance(result, tuple):
            if platform == "tiktok" and result[0] == "IP_BLOCKED":
                return await _send_error(
                    message,
                    "❗️TikTok блокирует IP сервера для этого видео. "
                    "Нужен прокси/VPN для контейнера app.",
                )
            if platform == "tiktok" and result[0] == "LOGIN_REQUIRED":
                return await _send_error(message, "❗️TikTok требует cookies/авторизацию для этого видео.")
            return await _send_error(message, f"❗️Ошибка при скачивании: {result}")

        file_path = result
        w, h = get_video_resolution(file_path)
        sent = await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)
        if not sent:
            return
        await _log_download(message, user_id, platform, url)

    except Exception as e:
        logger.error("❌ [DOWNLOAD] Ошибка при скачивании: %s", e, exc_info=True)
        await _send_error(message, f"❗️Ошибка при скачивании: {e}")
    finally:
        await set_busy(state, False)
