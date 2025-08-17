from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiogram.utils.markdown as markdown

import asyncio
import os

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

# Простая in-memory блокировка (вместо redis is_user_busy/...)
_busy: set[int] = set()
_pending_format_tasks: dict[int, asyncio.Task] = {}
_subscriber_selecting: set[int] = set()  # пользователи, ожидающие первый выбор формата

async def is_user_busy(user_id: int) -> bool:
    return user_id in _busy

async def set_user_busy(user_id: int) -> None:
    _busy.add(user_id)

async def clear_user_busy(user_id: int) -> None:
    _busy.discard(user_id)

def _schedule_format_timeout(user_id: int, bot, chat_id: int):
    # cancel previous if exists
    old = _pending_format_tasks.get(user_id)
    if old and not old.done():
        old.cancel()

    async def waiter():
        try:
            await asyncio.sleep(FORMAT_SELECTION_TIMEOUT)
            # if still busy (format not chosen) release
            if user_id in _busy:
                _busy.discard(user_id)
                try:
                    await bot.send_message(chat_id, '⌛️ Выбор формата отменён (таймаут). Отправьте ссылку снова.')
                except Exception:  # noqa: BLE001
                    pass
        except asyncio.CancelledError:  # noqa: PERF203
            return
        finally:
            _pending_format_tasks.pop(user_id, None)

    _pending_format_tasks[user_id] = asyncio.create_task(waiter())

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

    if await is_user_busy(user.id):
        await message.answer('⏳ Дождитесь завершения предыдущей загрузки.')
        return

    if is_yt_sub:
        # блокируем сразу, чтобы нельзя было слать новые ссылки параллельно
        await set_user_busy(user.id)
        await state.update_data({f'yt_url_{user.id}': url})
        _subscriber_selecting.add(user.id)
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text='Видео 240p', callback_data='yt_download:video_240'),
            InlineKeyboardButton(text='Видео 360p', callback_data='yt_download:video_360')
        )
        builder.row(
            InlineKeyboardButton(text='Видео 480p', callback_data='yt_download:video_480'),
            InlineKeyboardButton(text='Видео 720p', callback_data='yt_download:video_720')
        )
        builder.row(InlineKeyboardButton(text='Скачать аудио', callback_data='yt_download:audio'))
        await message.answer('Выберите формат скачивания (3 мин)...', reply_markup=builder.as_markup())
        _schedule_format_timeout(user.id, message.bot, message.chat.id)
        return

    await set_user_busy(user.id)
    if await check_download_limit(message, user.id):
        await clear_user_busy(user.id)
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
    if await is_user_busy(user.id):
        if user.id in _subscriber_selecting:
            # первый клик – разрешаем и снимаем флаг
            _subscriber_selecting.discard(user.id)
        else:
            return await callback.answer('⏳ Уже обрабатывается предыдущий выбор, дождитесь.')
    else:
        # (например, истёк таймер и busy снят) — ставим снова и продолжаем
        await set_user_busy(user.id)
    # отменяем таймер выбора формата
    task = _pending_format_tasks.pop(user.id, None)
    if task and not task.done():
        task.cancel()
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
        await clear_user_busy(user.id)
    _subscriber_selecting.discard(user.id)

