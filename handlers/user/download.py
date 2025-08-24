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

    # Универсальная обработка YouTube для всех пользователей
    if platform == 'youtube':
        try:
            wait_msg = await message.answer('⏳ Секунду...')
            downloader = YTDLPDownloader()
            max_filesize_mb = await get_max_filesize_mb(level, sub)
            info = await downloader.get_available_video_options(url)
            preview = info['thumbnail_url']
            
            # --- Формируем список разрешений и доступность ---
            unique_res = {}
            for fmt in info['formats']:
                if fmt.get('mime_type') == 'video/mp4':
                    res_str = fmt.get('res')
                    if res_str and res_str.endswith('p'):
                        try:
                            res_int = int(res_str.replace('p',''))
                            if 240 <= res_int <= 1080:
                                # приоритет progressive=True
                                if res_str not in unique_res or (fmt.get('progressive') and not unique_res[res_str].get('progressive')):
                                    unique_res[res_str] = fmt
                        except (ValueError, TypeError):
                            continue

            sorted_res = sorted(unique_res.items(), key=lambda x: int(x[0].replace('p','')))
            # Определяем максимальное разрешение
            max_res = max([int(r.replace('p','')) for r, _ in sorted_res], default=0)

            # --- Логика доступа ---
            def is_free(res):
                res_int = int(res.replace('p',''))
                if max_res >= 720:
                    return res_int in (240, 360, 480)
                elif max_res == 480:
                    return res_int in (240, 360)
                elif max_res == 360:
                    return res_int == 240
                else:
                    return False

            # --- Формируем текст с весом и смайликами ---
            lines = [f"<b>🎬 {info['title']}</b>\n"]
            lines.append("Приблизительные размеры:")
            for res, fmt in sorted_res:
                size_mb = fmt.get('size_mb') or (fmt.get('filesize', 0) / 1024 / 1024)
                size_str = f"{size_mb:.0f}MB" if size_mb else "?MB"
                if size_mb and max_filesize_mb and size_mb > max_filesize_mb:
                    emoji = '🔒'
                elif sub or is_free(res):
                    emoji = '⚡️'
                else:
                    emoji = '🔒'
                lines.append(f"{emoji}  {res}:  {size_str}")
            lines.append("")
            lines.append("<i>Выберите разрешение для скачивания видео или получите только аудио:</i>")
            
            # --- Клавиатура ---
            rows = []
            row = []
            for res, fmt in sorted_res:
                size_mb = fmt.get('size_mb') or (fmt.get('filesize', 0) / 1024 / 1024)
                # Если разрешение не free и нет подписки — всегда замок и ytlocked:sub
                if not (sub or is_free(res)):
                    emoji = '🔒'
                    cb = f"ytlocked:sub:{res}"
                # Если разрешение free или есть подписка — проверяем размер
                elif size_mb is not None and size_mb > max_filesize_mb:
                    emoji = '🔒'
                    cb = f"ytlocked:file:{res}"
                else:
                    emoji = '⚡️'
                    cb = f"ytres:{fmt['itag']}"
                row.append(InlineKeyboardButton(text=f"{emoji} {res}", callback_data=cb))
                if len(row) == 2:
                    rows.append(row)
                    row = []

            if row:
                rows.append(row)
            # Аудио всегда доступно
            rows.append([
                InlineKeyboardButton(
                    text="🎧 Аудио",
                    callback_data=f"ytdl:audio:{url}"
                )
            ])
            keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

            await state.update_data({"yt_url": url})
            await message.answer_photo(
                photo=preview,
                caption='\n'.join(lines),
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

@router.callback_query(lambda c: c.data.startswith('ytlocked:'))
async def ytlocked_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    Показывает причину блокировки: file — превышен лимит размера, sub — нужна подписка.
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="subscribe")]
    ])
    parts = callback.data.split(':', 2)
    reason = parts[1] if len(parts) > 1 else 'sub'
    if reason == 'file':
        text = ('🔒 Данное разрешение недоступно, так как файл слишком большой для вас.\n\n'
                'Повысьте реферальный уровень или оформите подписку для увеличения лимита.')
    else:
        text = ('🔒 Доступ к этому формату разрешения ограничен.\n\n'
                'Приобретите подписку, чтобы разблокировать.')
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

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

async def get_max_filesize_mb(level, sub):
    # Определение максимального размера файла в зависимости от уровня и подписки
    if level == 1:
        max_filesize_mb = DOWNLOAD_FILE_LIMIT
    elif level == 2:
        max_filesize_mb = DOWNLOAD_FILE_LIMIT * 3
    elif level == 3:
        max_filesize_mb = DOWNLOAD_FILE_LIMIT * 5
    else:
        max_filesize_mb = DOWNLOAD_FILE_LIMIT * 10
    return max_filesize_mb

async def process_youtube_or_other(message, url, user_id, platform, state, mode, level, sub):
    """Скачивает видео или аудио с учетом лимитов и статусов пользователя."""
    try:
        if platform == 'youtube':
            downloader = YTDLPDownloader()

            max_filesize_mb = await get_max_filesize_mb(level, sub)

            if mode == 'audio':
                file_path = await downloader.download_audio(url)
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