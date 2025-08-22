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
from services import get_downloader


logger = logging.getLogger(__name__)
router = Router()
BUSY_KEY = "busy"

async def strip_url_after_ampersand(url: str) -> str:
    """
    Возвращает url без аргументов после первого & (оставляет только до первого &).
    Например: https://youtube.com/watch?v=abc&list=xyz -> https://youtube.com/watch?v=abc
    """
    if '&' in url:
        return url.split('&', 1)[0]
    return url
    
@router.message(F.text.regexp(r'https?://'))
async def download_handler(message: types.Message, state: FSMContext):
    """Обрабатывает ссылку на скачивание, применяет лимиты и проверки."""
    url = message.text.strip()
    user = message.from_user
    platform = detect_platform(url)
    url = await strip_url_after_ampersand(url)

    # Проверка на параллельную загрузку
    data = await state.get_data()
    if data.get(BUSY_KEY, False):
        await message.answer('⏳ Уже выполняется другая загрузка. Пожалуйста, дождитесь завершения.')
        return
    await state.update_data({BUSY_KEY: True})

    async with get_session() as session:
        # Получение лимитов и статусов пользователя
        daily = await get_daily_downloads(session, user.id)
        sub = await is_subscriber(session, user.id)
        _, level, is_vip = await get_referral_stats(session, user.id)
        guard_on = await is_channel_guard_enabled(session)
        required_channels = await get_required_active_channels(session) if guard_on and not is_vip else []
    limit = DAILY_DOWNLOAD_LIMITS.get(level)

    # Проверка лимита скачиваний для обычных пользователей
    if not sub and limit is not None and daily >= limit:
        await message.answer(f'⚠️ Лимит {limit} скачиваний в день. Оформите подписку для безлимита.')
        await state.update_data({BUSY_KEY: False})
        return

    # Проверка подписки на обязательные каналы
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

    # Обработка YouTube для подписчиков: выбор качества и аудио
    if platform == 'youtube' and sub:
        try:
            wait_msg = await message.answer('⏳ Секунду...')
            downloader = YTDLPDownloader()
            
            max_filesize_mb = await get_max_filesize_mb(level, sub)

            info = await downloader.get_available_video_options(url, max_filesize_mb=max_filesize_mb) 
            text = (
                f"<b>🎬 {info['title']}</b>\n"
                f"\n"
                f"<i>Выберите разрешение для скачивания видео или получите только аудио:</i>\n"
                f"\n"
                f"<b>📥 Доступные разрешения:</b>"
            )

            unique_res = {}
            for fmt in info['formats']:
                if fmt.get('mime_type') != 'video/mp4':
                    continue

                res_str = fmt.get('res')
                if not res_str or not res_str.endswith('p'):
                    continue
                try:
                    res_int = int(res_str.replace('p',''))
                except (ValueError, TypeError):
                    continue
                if res_int < 240 or res_int > 1080:
                    continue
                if res_str not in unique_res or (fmt['progressive'] and not unique_res[res_str]['progressive']):
                    unique_res[res_str] = fmt

            sorted_res = sorted(unique_res.items(), key=lambda x: int(x[0].replace('p','')))

            rows = []
            row = []
            for res, fmt in sorted_res:
                row.append(
                    InlineKeyboardButton(
                        text=res,
                        callback_data=f"ytres:{fmt['itag']}"
                    )
                )
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)

            rows.append([
                InlineKeyboardButton(
                    text="🎧 Скачать аудио",
                    callback_data=f"ytdl:audio:{url}"
                )
            ])
            keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

            await state.update_data({"yt_url": url})
            await message.answer_photo(
                photo=info['thumbnail_url'],
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            try:
                await wait_msg.delete()
            except Exception:
                pass

        except Exception as e:
            await message.answer('Ошибка, пожалуйста, попробуйте позже')
            logger.error(f'❌ [DOWNLOAD] Ошибка при формировании кнопок: {e}', exc_info=True)

        await state.update_data({BUSY_KEY: False})
        return
    else:
        # Обычный пользователь YouTube — показать две кнопки: видео и аудио
        if platform == 'youtube':
            try:
                wait_msg = await message.answer('⏳ Секунду...')

                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📹 Скачать видео", callback_data=f"ytbasic:video:{url}")],
                        [InlineKeyboardButton(text="🎧 Скачать аудио", callback_data=f"ytbasic:audio:{url}")]
                    ]
                )
                await message.answer(
                    "<b>🎬 Видео найдено!</b>\n\n"
                    "<i>Выберите нужный вариант:</i>",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                await state.update_data({"yt_url": url})
                await state.update_data({BUSY_KEY: False})

                await wait_msg.delete()
                return
            except Exception as e:
                await message.answer('Ошибка, пожалуйста, проверьте позже')
                logger.error(f'❌ [DOWNLOAD] Ошибка при формировании кнопок: {e}', exc_info=True)
                await state.update_data({BUSY_KEY: False})
        else:
            try:
                await message.answer('⏳ Скачиваем...')
                await process_youtube_or_other(message, url, user.id, platform, state, 'video', level, sub)
                await state.update_data({BUSY_KEY: False})
                return
            except Exception as e:
                await message.answer('Ошибка, пожалуйста, попробуйте позже')
                logger.error(f'❌ [DOWNLOAD] Ошибка при скачивании видео: {e}', exc_info=True)
                await state.update_data({BUSY_KEY: False})

@router.callback_query(lambda c: c.data.startswith('ytres:'))
async def ytres_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор разрешения YouTube-видео."""
    # Обработка выбора разрешения YouTube
    _, itag = callback.data.split(':', 1)
    user = callback.from_user
    await state.update_data({BUSY_KEY: True})
    await callback.message.answer('⏳ Скачиваем видео, подождите пару минут...')
    data = await state.get_data()
    url = data.get("yt_url")

    async with get_session() as session:
        _, level, _ = await get_referral_stats(session, user.id)
        sub = await is_subscriber(session, user.id)

    await process_youtube_or_other(callback.message, url, user.id, 'youtube', state, itag, level, sub)

@router.callback_query(lambda c: c.data.startswith('ytdl:'))
async def ytdl_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает скачивание только аудио с YouTube."""
    # Обработка скачивания только аудио с YouTube
    _, mode, url = callback.data.split(':', 2)
    user = callback.from_user
    await state.update_data({BUSY_KEY: True})
    await callback.message.answer('⏳ Скачиваем...')
    async with get_session() as session:
        _, level, _ = await get_referral_stats(session, user.id)
    await process_youtube_or_other(callback.message, url, user.id, 'youtube', state, mode, level, True)


# --- Новый обработчик для обычных пользователей YouTube ---
@router.callback_query(lambda c: c.data.startswith('ytbasic:'))
async def ytbasic_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает кнопки 'Скачать видео' и 'Скачать аудио' для обычных пользователей YouTube."""
    _, mode, url = callback.data.split(':', 2)
    user = callback.from_user
    await state.update_data({BUSY_KEY: True})

    async with get_session() as session:
        _, level, _ = await get_referral_stats(session, user.id)

    if mode == 'video':
        await callback.message.answer('⏳ Скачиваем видео, подождите пару минут...')
        await process_youtube_or_other(callback.message, url, user.id, 'youtube', state, 'video', level, False)
    elif mode == 'audio':
        await callback.message.answer('⏳ Скачиваем аудио...')
        await process_youtube_or_other(callback.message, url, user.id, 'youtube', state, 'audio', level, False)
    else:
        await callback.answer('Неизвестный режим', show_alert=True)
        await state.update_data({BUSY_KEY: False})

async def get_max_filesize_mb(level, sub):
    # Определение максимального размера файла в зависимости от уровня и подписки
    if level == 1:
        max_filesize_mb = DOWNLOAD_FILE_LIMIT
    elif level == 2:
        max_filesize_mb = DOWNLOAD_FILE_LIMIT * 3
    elif level >= 3 or sub:
        max_filesize_mb = DOWNLOAD_FILE_LIMIT * 7
    return max_filesize_mb

async def process_youtube_or_other(message, url, user_id, platform, state, mode, level, sub):
    """Скачивает видео или аудио с учетом лимитов и статусов пользователя."""
    try:
        if platform == 'youtube':
            downloader = YTDLPDownloader()

            max_filesize_mb = await get_max_filesize_mb(level, sub)

            if mode == 'audio':
                file_path = await downloader.download_audio(url, user_id, message)
                await send_audio(message.bot, message, message.chat.id, file_path)
            
            elif mode.isdigit():
        
                result = await downloader.download_by_itag(url, int(mode), message, user_id)
                if isinstance(result, tuple) and result[0] == 'DENIED_SIZE':
                    # Превышен лимит размера файла
                    await message.answer(f'⚠️ Видео слишком большое: {result[1]} МБ. Ваш лимит — {max_filesize_mb} МБ. Оформите подписку для снятия ограничений.')
                    await state.update_data({BUSY_KEY: False})
                    return
                file_path = result
                w, h = get_video_resolution(file_path)
                await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)
            else:
                result = await downloader.download(url, message, user_id)
                if isinstance(result, tuple) and result[0] == 'DENIED_SIZE':
                    # Превышен лимит размера файла
                    await message.answer(f'⚠️ Видео слишком большое: {result[1]} МБ. Ваш лимит — {max_filesize_mb} МБ. Оформите подписку для снятия ограничений.')
                    await state.update_data({BUSY_KEY: False})
                    return
                file_path = result
                w, h = get_video_resolution(file_path)
                await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)
        
        else:
            # Скачивание с других платформ
            downloader = get_downloader(url)
            file_path = await downloader.download(url, user_id)
            w, h = get_video_resolution(file_path)
            await send_video(message.bot, message, message.chat.id, user_id, file_path, w, h)

        async with get_session() as session:
            await add_or_update_user(session, user_id, getattr(message.from_user, 'first_name', None), getattr(message.from_user, 'username', None))
            await log_user_activity(session, user_id)
            await increment_platform_download(session, user_id, platform)
    except Exception as e:
        logger.error(f'❌ [DOWNLOAD] Ошибка при скачивании: {e}')
        await message.answer('❗️ Ошибка при скачивании, попробуйте позже.')
    finally:
        await state.update_data({BUSY_KEY: False})