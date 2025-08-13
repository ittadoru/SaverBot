
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from handlers.admin.history import HistoryStates
from utils import logger as log
from utils.platform_detect import detect_platform
from utils.video_utils import get_video_resolution
from utils.send import send_video, send_audio
from services.youtube.pytube_downloader import PyTubeDownloader
from services.youtube.yt_dlp_downloader import YTDLPDownloader
from services import get_downloader
from config import USE_PYTUBE, ADMIN_ERROR
import asyncio
from redis_db.download import increment_daily_download, increment_download, get_daily_downloads
from redis_db.subscribers import is_subscriber
from redis_db.platforms import increment_platform_download
from redis_db.users import log_user_activity, push_recent_link, is_user_busy, set_user_busy, clear_user_busy


router = Router()



@router.message(F.text.regexp(r'https?://') & ~F.state.in_([HistoryStates.waiting_for_id_or_username]))
async def download_handler(message: types.Message, state: FSMContext):
    """
    Обработчик сообщений с URL. Если это YouTube и пользователь подписчик, предлагает выбор качества.
    Для остальных платформ или неподписчиков скачивает видео напрямую через yt-dlp.
    """
    url = message.text.strip()
    user = message.from_user
    platform = detect_platform(url)
    is_yt_sub = platform == "youtube" and await is_subscriber(user.id)

    if await is_user_busy(user.id):
        await message.answer("⏳ Пожалуйста, дождитесь завершения предыдущей загрузки.")
        return

    if is_yt_sub:
        await state.update_data({f"yt_url_{user.id}": url})
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Видео 240p", callback_data="yt_download:video_240"),
             InlineKeyboardButton(text="Видео 360p", callback_data="yt_download:video_360")],
            [InlineKeyboardButton(text="Видео 480p", callback_data="yt_download:video_480"),
             InlineKeyboardButton(text="Видео 720p", callback_data="yt_download:video_720")],
            [InlineKeyboardButton(text="Скачать аудио", callback_data="yt_download:audio")]
        ])
        await message.answer("Выберите формат скачивания:", reply_markup=keyboard)
        return

    await set_user_busy(user.id)
    if await check_download_limit(message, user.id):
        await clear_user_busy(user.id)
        return
    await message.answer("⏳ Подождите немножко, видео скачивается...")
    await process_download(message, url, user.id, platform)
async def check_download_limit(message, user_id):
    daily_downloads = await get_daily_downloads(user_id)
    if daily_downloads >= 20 and not await is_subscriber(user_id):
        await message.answer("⚠️ Вы достигли лимита скачиваний на сегодня (20). Попробуйте завтра или оформите подписку!")
        return True
    return False

async def process_download(message, url, user_id, platform):
    try:
        downloader = get_downloader(url)
        if platform == "youtube":
            file_path = await downloader.download(url, user_id, message)
        else:
            file_path = await downloader.download(url, user_id)
        # Если файл не скачан (age-restricted), просто сообщаем пользователю и выходим
        if file_path is None:
            await message.answer("🚫 Это видео недоступно для скачивания, так как имеет возрастные ограничения или требует авторизации в Instagram.")
            await clear_user_busy(user_id)
            return
        width, height = get_video_resolution(file_path)
        asyncio.create_task(send_video(message.bot, message, message.chat.id, user_id, file_path, width, height))
        await log_user_activity(user_id)
        await push_recent_link(user_id, url)
        await increment_download(platform, user_id=user_id)
        await increment_platform_download(user_id, platform)
        await increment_daily_download(user_id=user_id)
        await clear_user_busy(user_id)
    except Exception as e:
        await clear_user_busy(user_id)
        log.log_error(f"Ошибка при скачивании: {e}")
        await message.answer(f"❗️ Произошла ошибка при скачивании, пожалуйста, попробуйте позже.")
        await message.bot.send_message(ADMIN_ERROR, f"Ошибка при скачивании: {e}")



@router.callback_query(lambda c: c.data.startswith("yt_download:"))
async def yt_download_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик выбора формата скачивания видео с YouTube.
    Использует pytube, если включено, с fallback на yt-dlp.
    """
    format_type = callback.data.split(":")[1]
    user = callback.from_user
    url = (await state.get_data()).get(f"yt_url_{user.id}")
    if not url:
        return await callback.answer("Ссылка не найдена.")
    if await is_user_busy(user.id):
        return await callback.message.answer("⏳ Пожалуйста, дождитесь завершения предыдущей загрузки.")
    await set_user_busy(user.id)
    await callback.message.answer("⏳ Скачиваем...")
    try:
        file_path = None
        yt_dlp_dl = YTDLPDownloader()
        pytube_dl = PyTubeDownloader() if USE_PYTUBE else None
        if format_type.startswith("video_"):
            res = format_type.split('_')[1]
            if USE_PYTUBE:
                file_path = await pytube_dl.download(url, resolution=res)
            if not file_path:
                res_map_dl = {
                    "240": 'bestvideo[ext=mp4][vcodec^=avc1][height<=240]+bestaudio[ext=m4a]/best[ext=mp4]',
                    "360": 'bestvideo[ext=mp4][vcodec^=avc1][height<=360]+bestaudio[ext=m4a]/best[ext=mp4]',
                    "480": 'bestvideo[ext=mp4][vcodec^=avc1][height<=480]+bestaudio[ext=m4a]/best[ext=mp4]',
                    "720": 'bestvideo[ext=mp4][vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]',
                }
                file_path = await yt_dlp_dl.download(
                    url, user.id, callback.message, custom_format=res_map_dl.get(res, res_map_dl["480"])
                )
            width, height = get_video_resolution(file_path)
            asyncio.create_task(send_video(callback.bot, callback.message, callback.message.chat.id, user.id, file_path, width, height))
        elif format_type == "audio":
            if USE_PYTUBE:
                file_path = await pytube_dl.download_audio(url)
            if not file_path:
                file_path = await yt_dlp_dl.download_audio(url, user.id)
            asyncio.create_task(send_audio(callback.bot, callback.message, callback.message.chat.id, file_path))
        else:
            await clear_user_busy(user.id)
            return await callback.answer("Неизвестный формат.")
        await log_user_activity(user.id)
        await push_recent_link(user.id, url)
        await increment_download("youtube", user_id=user.id)
        await clear_user_busy(user.id)
    except Exception as e:
        await clear_user_busy(user.id)
        import traceback
        error_text = f"Ошибка: {e}"
        full_trace = traceback.format_exc()
        log.log_error(error_text)
        log.log_error(full_trace)
        try:
            await callback.message.bot.send_message(
                ADMIN_ERROR,
                f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                parse_mode="HTML"
            )
        except Exception as send_err:
            log.log_error(f"Не удалось отправить ошибку админу: {send_err}")
