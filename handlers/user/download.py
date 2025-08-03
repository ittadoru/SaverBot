from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from handlers.admin.history import HistoryStates
from utils.redis import is_subscriber, log_user_activity, push_recent_link, increment_download
from utils.platform_detect import detect_platform
from utils import logger as log
from utils.video_utils import get_video_resolution
from utils.send import send_video, send_audio
from services.youtube.pytube_downloader import PyTubeDownloader
from services.youtube.yt_dlp_downloader import YTDLPDownloader
from config import USE_PYTUBE
import asyncio
from config import ADMIN_ERROR


router = Router()

@router.message(F.text.regexp(r'https?://') & ~F.state.in_([HistoryStates.waiting_for_id_or_username]))
async def download_handler(message: types.Message, state: FSMContext):
    url = message.text.strip()
    user = message.from_user
    platform = detect_platform(url)
    if platform == "youtube" and await is_subscriber(user.id):
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

    await message.answer("⏳ Подождите немножко, видео скачивается...")
    try:
        downloader = YTDLPDownloader()  # fallback для всех остальных платформ
        file_path = await downloader.download(url, user.id)
        width, height = get_video_resolution(file_path)
        asyncio.create_task(send_video(message.bot, message.chat.id, user.id, file_path, width, height))
        await log_user_activity(user.id)
        await push_recent_link(user.id, url)
        await increment_download(platform, user_id=user.id)
    except Exception as e:
        import traceback
        error_text = f"Ошибка: {e}"
        full_trace = traceback.format_exc()
        log.log_error(error_text)
        log.log_error(full_trace)
        # Отправка сообщения админу (замените на нужный ID)
        try:
            await message.bot.send_message(
                ADMIN_ERROR,
                f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                parse_mode="HTML"
            )
        except Exception as send_err:
            log.log_error(f"Не удалось отправить ошибку админу: {send_err}")


@router.callback_query(lambda c: c.data.startswith("yt_download:"))
async def yt_download_callback(callback: types.CallbackQuery, state: FSMContext):
    format_type = callback.data.split(":")[1]
    user = callback.from_user
    url = (await state.get_data()).get(f"yt_url_{user.id}")
    if not url:
        return await callback.answer("Ссылка не найдена.")
    await callback.message.answer("⏳ Скачиваем...")

    try:
        print(USE_PYTUBE)
        file_path = None
        yt_dlp_dl = YTDLPDownloader()
        pytube_dl = PyTubeDownloader() if USE_PYTUBE else None

        if format_type.startswith("video_"):
            res_map = {
                "240": 240,
                "360": 360,
                "480": 480,
                "720": 720,
            }
            res = format_type.split('_')[1]

            if USE_PYTUBE:
                try:
                    log.log_message(f"Попытка скачать видео через pytube: {url}, качество {res_map.get(res, 480)}p")
                    file_path = await pytube_dl.download(url, resolution=res)
                    log.log_message(f"Видео скачано через pytube: {file_path}")
                except Exception as e:
                    log.log_error(e, user.username, f"Ошибка pytube, fallback на yt-dlp: {url}")
            
            if not file_path:
                res_map_dl = {
                    "240": 'bestvideo[ext=mp4][vcodec^=avc1][height<=240]+bestaudio[ext=m4a]/best[ext=mp4]',
                    "360": 'bestvideo[ext=mp4][vcodec^=avc1][height<=360]+bestaudio[ext=m4a]/best[ext=mp4]',
                    "480": 'bestvideo[ext=mp4][vcodec^=avc1][height<=480]+bestaudio[ext=m4a]/best[ext=mp4]',
                    "720": 'bestvideo[ext=mp4][vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]',
                }
                file_path = await yt_dlp_dl.download(url, user.id, custom_format=res_map_dl.get(res, res_map_dl["480"]), message=callback.message)

            width, height = get_video_resolution(file_path)
            asyncio.create_task(send_video(callback.bot, callback.message.chat.id, user.id, file_path, width, height))

        elif format_type == "audio":
            if USE_PYTUBE:
                try:
                    log.log_message(f"Попытка скачать аудио через pytube: {url}")
                    file_path = await pytube_dl.download_audio(url)
                    log.log_message(f"Аудио скачано через pytube: {file_path}")
                except Exception as e:
                    log.log_error(e, user.username, f"Ошибка pytube, fallback на yt-dlp: {url}")
            
            if not file_path:
                file_path = await yt_dlp_dl.download_audio(url, user.id)

            asyncio.create_task(send_audio(callback.bot, callback.message.chat.id, file_path))

        else:
            return await callback.answer("Неизвестный формат.")

        await log_user_activity(user.id)
        await push_recent_link(user.id, url)
        await increment_download("youtube", user_id=user.id)

    except Exception as e:
        import traceback
        error_text = f"Ошибка: {e}"
        full_trace = traceback.format_exc()
        log.log_error(error_text)
        log.log_error(full_trace)
        # Отправка сообщения админу (замените на нужный ID)
        try:
            await callback.message.bot.send_message(
                ADMIN_ERROR,
                f"❗️Произошла ошибка:\n<pre>{error_text}</pre>\n<pre>{full_trace}</pre>",
                parse_mode="HTML"
            )
        except Exception as send_err:
            log.log_error(f"Не удалось отправить ошибку админу: {send_err}")
