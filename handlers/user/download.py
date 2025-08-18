
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiogram.utils.markdown as markdown
import asyncio
import os
from typing import Optional

from utils.platform_detect import detect_platform
from utils.video_utils import get_video_resolution
from utils.send import send_video, send_audio
from services import get_downloader
from services.youtube import YTDLPDownloader
from utils import logger as log
from db.base import get_session
from db.subscribers import is_subscriber
from db.users import log_user_activity, add_or_update_user
from db.channels import is_channel_guard_enabled, get_required_active_channels, check_user_memberships
from db.downloads import get_daily_downloads, increment_daily_download, increment_download, add_download_link
from db.platforms import increment_platform_download
from config import PRIMARY_ADMIN_ID, MAX_FREE_VIDEO_MB

router = Router()

FREE_DAILY_LIMIT = 20
FORMAT_SELECTION_TIMEOUT = 180  # seconds to wait for subscriber to pick YouTube format


# FSMContext-based busy/timeout management
BUSY_KEY = "busy"
PENDING_TASKS_KEY = "pending_format_tasks"
SUBSCRIBER_SELECTING_KEY = "subscriber_selecting"

def get_format_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text='Видео 240p', callback_data='yt_download:video_240'),
        InlineKeyboardButton(text='Видео 360p', callback_data='yt_download:video_360')
    )
    kb.row(
        InlineKeyboardButton(text='Видео 480p', callback_data='yt_download:video_480'),
        InlineKeyboardButton(text='Видео 720p', callback_data='yt_download:video_720')
    )
    kb.row(InlineKeyboardButton(text='Скачать аудио', callback_data='yt_download:audio'))
    return kb

async def is_user_busy(state: FSMContext) -> bool:
    data = await state.get_data()
    return data.get(BUSY_KEY, False)

async def set_user_busy(state: FSMContext, value: bool = True) -> None:
    await state.update_data({BUSY_KEY: value})

async def clear_user_busy(state: FSMContext) -> None:
    await state.update_data({BUSY_KEY: False})

async def set_pending_task(state: FSMContext, task: asyncio.Task) -> None:
    await state.update_data({PENDING_TASKS_KEY: task})

async def get_pending_task(state: FSMContext) -> Optional[asyncio.Task]:
    data = await state.get_data()
    return data.get(PENDING_TASKS_KEY)

async def clear_pending_task(state: FSMContext) -> None:
    await state.update_data({PENDING_TASKS_KEY: None})

async def set_subscriber_selecting(state: FSMContext, value: bool = True) -> None:
    await state.update_data({SUBSCRIBER_SELECTING_KEY: value})

async def is_subscriber_selecting(state: FSMContext) -> bool:
    data = await state.get_data()
    return data.get(SUBSCRIBER_SELECTING_KEY, False)

async def clear_subscriber_selecting(state: FSMContext) -> None:
    await state.update_data({SUBSCRIBER_SELECTING_KEY: False})

def _schedule_format_timeout(user_id: int, bot, chat_id: int, state: FSMContext):
    async def waiter():
        try:
            await asyncio.sleep(FORMAT_SELECTION_TIMEOUT)
            if await is_user_busy(state):
                await clear_user_busy(state)
                try:
                    await bot.send_message(chat_id, '⌛️ Выбор формата отменён (таймаут). Отправьте ссылку снова.')
                except Exception:
                    pass
        except asyncio.CancelledError:
            return
        finally:
            await clear_pending_task(state)
    task = asyncio.create_task(waiter())
    asyncio.create_task(set_pending_task(state, task))

@router.message(F.text.regexp(r'https?://'))
async def download_handler(message: types.Message, state: FSMContext):

    url = message.text.strip()
    user = message.from_user
    platform = detect_platform(url)

    # --- Глобальное ограничение и подписка на каналы ---
    async with get_session() as session:
        guard_on = await is_channel_guard_enabled(session)
        if guard_on:
            required_channels = await get_required_active_channels(session)
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
                    return

    # корректная проверка подписки (нужна сессия)
    if platform == 'youtube':
        async with get_session() as session:
            is_yt_sub = await is_subscriber(session, user.id)
    else:
        is_yt_sub = False


    if await is_user_busy(state):
        await message.answer('⏳ Дождитесь завершения предыдущей загрузки.')
        return

    if is_yt_sub:
        await set_user_busy(state, True)
        await state.update_data({f'yt_url_{user.id}': url})
        await set_subscriber_selecting(state, True)
        kb = get_format_keyboard()
        await message.answer('Выберите формат скачивания (3 мин)...', reply_markup=kb.as_markup())
        _schedule_format_timeout(user.id, message.bot, message.chat.id, state)
        return

    await set_user_busy(state, True)
    if await check_download_limit(message, user.id):
        await clear_user_busy(state)
        return
    await message.answer('⏳ Скачиваем...')
    await process_download(message, url, user.id, platform)

async def check_download_limit(message: types.Message, user_id: int) -> bool:
    async with get_session() as session:
        daily = await get_daily_downloads(session, user_id)
        sub = await is_subscriber(session, user_id)
    if daily >= FREE_DAILY_LIMIT and not sub:
        await message.answer('⚠️ Лимит 20 скачиваний в день. Оформите подписку для безлимита.')
        return True
    return False

def _normalize_download_result(result):
    """Приводит результат download() к строке пути либо возвращает спец-кортеж DENIED_SIZE.

    Возможные варианты:
      * 'path/to/file.mp4' – обычный случай.
      * ('DENIED_SIZE', size_mb_str) – отказ.
      * ('path/to/file.mp4', job_id) – большой файл с прогрессом.
    Возвращаем либо ('DENIED_SIZE', size), либо строковый путь.
    """
    if isinstance(result, tuple):
        if result and result[0] == 'DENIED_SIZE':
            return result  # оставляем как есть
        # предполагаем (path, job_id)
        if len(result) == 2 and isinstance(result[0], str):
            return result[0]
    return result


async def process_download(message: types.Message, url: str, user_id: int, platform: str):
    try:
        downloader = get_downloader(url)
        async with get_session() as session:
            # гарантируем наличие пользователя
            await add_or_update_user(session, user_id, message.from_user.first_name, message.from_user.username)
            if platform == 'youtube':
                raw_result = await downloader.download(url, user_id, message)
                normalized = _normalize_download_result(raw_result)
                if isinstance(normalized, tuple) and normalized and normalized[0] == 'DENIED_SIZE':
                    size_mb = normalized[1]
                    builder = InlineKeyboardBuilder()
                    builder.button(text='💳 Подписка', callback_data='subscribe:open')
                    await message.answer(
                        f'🚫 Видео больше лимита {MAX_FREE_VIDEO_MB} МБ (это {size_mb} МБ) и недоступно бесплатно. Оформите подписку.',
                        reply_markup=builder.as_markup()
                    )
                    return
                file_path = normalized
            else:
                file_path = await downloader.download(url, user_id)
        if file_path is None:
            await message.answer('🚫 Видео недоступно (возрастное ограничение или требуется авторизация).')
            return
        w, h = get_video_resolution(file_path)
        asyncio.create_task(send_video(message.bot, message, message.chat.id, user_id, file_path, w, h))
        async with get_session() as session:
            await log_user_activity(session, user_id)
            await increment_download(session, user_id)
            await increment_platform_download(session, user_id, platform)
            await increment_daily_download(session, user_id)  # теперь всегда для всех
            await add_download_link(session, user_id, url)
    except Exception as e:  # noqa: BLE001
        log.log_error(f'Ошибка при скачивании: {e}')
        await message.answer('❗️ Ошибка при скачивании, попробуйте позже.')
        try:
            await message.bot.send_message(PRIMARY_ADMIN_ID, f'Ошибка при скачивании: {e}')
        except Exception:  # noqa: BLE001
            pass
    finally:
        await clear_user_busy(user_id)


@router.callback_query(lambda c: c.data.startswith('yt_download:'))
async def yt_download_callback(callback: types.CallbackQuery, state: FSMContext):
    fmt = callback.data.split(':')[1]
    user = callback.from_user
    url = (await state.get_data()).get(f'yt_url_{user.id}')
    if not url:
        return await callback.answer('Ссылка не найдена.')
    # Антиспам: допускаем только один валидный клик по кнопке формата/аудио
    if await is_user_busy(state):
        if await is_subscriber_selecting(state):
            await clear_subscriber_selecting(state)
        else:
            return await callback.answer('⏳ Уже обрабатывается предыдущий выбор, дождитесь.')
    else:
        await set_user_busy(state, True)
    # отменяем таймер выбора формата
    task = await get_pending_task(state)
    if task and not task.done():
        task.cancel()
    await clear_pending_task(state)
    await callback.message.answer('⏳ Скачиваем...')
    try:
        yt = YTDLPDownloader()
        if fmt.startswith('video_'):
            res = fmt.split('_')[1]
            res_map = {
                '240': 'bestvideo[ext=mp4][vcodec^=avc1][height<=240]+bestaudio[ext=m4a]/best[ext=mp4]',
                '360': 'bestvideo[ext=mp4][vcodec^=avc1][height<=360]+bestaudio[ext=m4a]/best[ext=mp4]',
                '480': 'bestvideo[ext=mp4][vcodec^=avc1][height<=480]+bestaudio[ext=m4a]/best[ext=mp4]',
                '720': 'bestvideo[ext=mp4][vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]',
            }
            raw_result = await yt.download(url, user.id, callback.message, custom_format=res_map.get(res, res_map['480']))
            normalized = _normalize_download_result(raw_result)
            if isinstance(normalized, tuple) and normalized and normalized[0] == 'DENIED_SIZE':
                size_mb = normalized[1]
                builder = InlineKeyboardBuilder()
                builder.button(text='💳 Подписка', callback_data='subscribe:open')
                await callback.message.answer(
                    f'🚫 Видео больше лимита {MAX_FREE_VIDEO_MB} МБ (это {size_mb} МБ) и недоступно бесплатно.',
                    reply_markup=builder.as_markup()
                )
                return
            path = normalized
            w, h = get_video_resolution(path)
            asyncio.create_task(send_video(callback.bot, callback.message, callback.message.chat.id, user.id, path, w, h))
        elif fmt == 'audio':
            path = await yt.download_audio(url, user.id)
            asyncio.create_task(send_audio(callback.bot, callback.message, callback.message.chat.id, path))
        else:
            return await callback.answer('Неизвестный формат.')
        async with get_session() as session:
            await log_user_activity(session, user.id)
            await increment_download(session, user.id)
            await increment_platform_download(session, user.id, 'youtube')
            await increment_daily_download(session, user.id)  # теперь всегда для всех
            await add_download_link(session, user.id, url)
    except Exception as e:  # noqa: BLE001
        log.log_error(f'Ошибка: {e}')
        try:
            await callback.message.answer('❗️ Ошибка при скачивании.')
        except Exception:
            pass
    finally:
        await clear_user_busy(state)
    await clear_subscriber_selecting(state)

