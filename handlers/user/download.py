

import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
import aiogram.utils.markdown as markdown
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.platform_detect import detect_platform
from utils.video_utils import get_video_resolution
from utils.send import send_video, send_audio
from services.youtube import YTDLPDownloader
from db.base import get_session
from db.subscribers import is_subscriber
from db.downloads import get_daily_downloads
from db.users import log_user_activity, add_or_update_user
from db.channels import is_channel_guard_enabled, get_required_active_channels, check_user_memberships
from db.platforms import increment_platform_download
from handlers.user.referral import get_referral_stats
from config import DAILY_DOWNLOAD_LIMITS, DOWNLOAD_FILE_LIMIT

logger = logging.getLogger(__name__)
router = Router()
BUSY_KEY = "busy"


# --- Основной обработчик ---
@router.message(F.text.regexp(r'https?://'))
async def download_handler(message: types.Message, state: FSMContext):
    url = message.text.strip()
    user = message.from_user
    platform = detect_platform(url)

    # Проверка на занятость
    data = await state.get_data()
    if data.get(BUSY_KEY, False):
        await message.answer('⏳ Уже выполняется другая загрузка. Пожалуйста, дождитесь завершения.')
        return
    await state.update_data({BUSY_KEY: True})

    # Проверка лимита и уровня
    async with get_session() as session:
        daily = await get_daily_downloads(session, user.id)
        sub = await is_subscriber(session, user.id)
        _, level, is_vip = await get_referral_stats(session, user.id)
        guard_on = await is_channel_guard_enabled(session)
        required_channels = await get_required_active_channels(session) if guard_on and not is_vip else []
    limit = DAILY_DOWNLOAD_LIMITS.get(level)
    if not sub and limit is not None and daily >= limit:
        await message.answer(f'⚠️ Лимит {limit} скачиваний в день. Оформите подписку для безлимита.')
        await state.update_data({BUSY_KEY: False})
        return

    # Проверка подписки на каналы (если нужно)
    if required_channels:
        bot = message.bot
        check_results = await check_user_memberships(bot, user.id, required_channels)
        not_joined = [ch for ch, res in zip(required_channels, check_results) if not res.is_member]
        if not_joined:
            text = "<b>Для скачивания необходимо подписаться на каналы:</b>\n\n"
            for ch in not_joined:
                link = markdown.hlink(f"@{ch.username}", f"https://t.me/{ch.username}")
                text += f"{link}\n"
            text += "\nПосле подписки — отправьте ссылку ещё раз."
            await message.answer(text, parse_mode="HTML")
            await state.update_data({BUSY_KEY: False})
            return

    # YouTube: если подписчик — две кнопки, иначе сразу скачиваем с ограничением
    if platform == 'youtube' and sub:
        try:
            downloader = YTDLPDownloader()

            if level == 1:
                max_filesize_mb = DOWNLOAD_FILE_LIMIT
            elif level == 2:
                max_filesize_mb = DOWNLOAD_FILE_LIMIT * 3
            elif level >= 3 or sub:
                max_filesize_mb = DOWNLOAD_FILE_LIMIT * 7

            info = await downloader.get_available_video_options(url, max_filesize_mb=max_filesize_mb) 
    
            text = (
                f"Название: \n"
                f"{info['title']}\n\n"
                f"Доступные разрешения:"
            )
            unique_res = {}
            for fmt in info['formats']:
                res = fmt['res']
                # Если такого разрешения ещё нет, или если новый вариант progressive — заменяем
                if res not in unique_res or (fmt['progressive'] and not unique_res[res]['progressive']):
                    unique_res[res] = fmt
            
            buttons = [
                [InlineKeyboardButton(
                    text=res,
                    callback_data=f"ytres:{fmt['itag']}"
                )]
                for res, fmt in unique_res.items()
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
            await message.answer_photo(
                photo=info['thumbnail_url'],
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception:
            await message.answer('Ошибка при формировании кнопок')

        await state.update_data({BUSY_KEY: False})
        return

    # Для всех остальных случаев — сразу скачиваем видео
    await message.answer('⏳ Скачиваем...')
    await process_youtube_or_other(message, url, user.id, platform, state, 'video', level, sub)


# --- Callback для YouTube кнопок ---
@router.callback_query(lambda c: c.data.startswith('ytdl:'))
async def ytdl_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    _, mode, url = callback.data.split(':', 2)
    user = callback.from_user
    await state.update_data({BUSY_KEY: True})
    await callback.message.answer('⏳ Скачиваем...')
    # Получаем уровень и подписку
    async with get_session() as session:
        _, level, _ = await get_referral_stats(session, user.id)
        sub = await is_subscriber(session, user.id)
    await process_youtube_or_other(callback.message, url, user.id, 'youtube', state, mode, level, sub)


# --- Универсальная функция скачивания ---
async def process_youtube_or_other(message, url, user_id, platform, state, mode, level, sub):
    try:
        if platform == 'youtube':
            from services.youtube import YTDLPDownloader
            downloader = YTDLPDownloader()
            max_mb = None
            if not sub:
                if level == 1:
                    max_mb = 100
                elif level == 2:
                    max_mb = 300
            if mode == 'audio':
                file_path = await downloader.download_audio(url, user_id, message)
                await send_audio(message.bot, message, message.chat.id, file_path)
            else:
                result = await downloader.download(url, message, user_id)
                if isinstance(result, tuple) and result[0] == 'DENIED_SIZE':
                    await message.answer(f'⚠️ Видео слишком большое: {result[1]} МБ. Ваш лимит — {max_mb or "безлимит"} МБ. Оформите подписку для снятия ограничений.')
                    await state.update_data({BUSY_KEY: False})
                    return
                file_path = result
                w, h = get_video_resolution(file_path)
                await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)
        else:
            from services import get_downloader
            downloader = get_downloader(url)
            file_path = await downloader.download(url, user_id)
            w, h = get_video_resolution(file_path)
            await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)
        async with get_session() as session:
            await add_or_update_user(session, user_id, getattr(message.from_user, 'first_name', None), getattr(message.from_user, 'username', None))
            await log_user_activity(session, user_id)
            await increment_platform_download(session, user_id, platform)
    except Exception as e:
        logger.error(f'Ошибка при скачивании: {e}')
        try:
            await message.answer('❗️ Ошибка при скачивании, попробуйте позже.')
        except Exception:
            pass
    finally:
        await state.update_data({BUSY_KEY: False})




