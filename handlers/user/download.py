import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from utils.download_files.clean_url import strip_url_after_ampersand
from utils.platform_detect import detect_platform
from utils.download_files.download_manager import (
    is_busy, set_busy, check_download_permissions, process_youtube_or_other
)
from utils.download_files.youtube_utils import prepare_youtube_menu
from utils.keyboards import subscribe_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text.regexp(r'https?://'))
async def download_handler(message: types.Message, state: FSMContext):
    """Обрабатывает ссылку на скачивание, применяет лимиты и проверки."""
    url = strip_url_after_ampersand(message.text.strip())
    user = message.from_user

    # Проверка на параллельную загрузку
    if await is_busy(state):
        return await message.answer("⏳ Уже выполняется другая загрузка.")
    await set_busy(state, True)

    wait_message = await message.answer("⏳ Секунду...")

    try:
        # Проверка лимитов, подписки, каналов
        can_download, reason = await check_download_permissions(user.id)
        if not can_download:
            return await message.answer(reason, parse_mode="HTML")

        platform = detect_platform(url)

        if platform == "youtube":
            keyboard, caption, preview = await prepare_youtube_menu(url, user.id)
            await state.update_data({"yt_url": url})
            return await message.answer_photo(
                photo=preview,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="HTML",
            )

        await wait_message.delete()

        # остальные платформы — сразу качаем
        await process_youtube_or_other(message, url, user.id, platform, state)

    except Exception as e:
        logger.error(f"❌ Ошибка в download_handler: {e}", exc_info=True)
        await message.answer("❗️ Ошибка при скачивании, попробуйте позже.")
    finally:
        await set_busy(state, False)


@router.callback_query(lambda c: c.data.startswith("ytres:"))
async def ytres_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Выбор разрешения YouTube-видео."""
    _, itag = callback.data.split(":", 1)
    user = callback.from_user

    await set_busy(state, True)
    await callback.message.answer("⏳ Скачиваем видео, подождите...")

    data = await state.get_data()
    url = data.get("yt_url")

    await process_youtube_or_other(callback.message, url, user.id, "youtube", state, itag)


@router.callback_query(lambda c: c.data.startswith("ytlocked:"))
async def ytlocked_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Причина блокировки (нужна подписка или превышен размер)."""
    parts = callback.data.split(":", 2)
    reason = parts[1] if len(parts) > 1 else "sub"

    if reason == "file":
        text = ("🔒 Данное разрешение недоступно: файл слишком большой.\n\n"
                "Повысьте уровень или оформите подписку для увеличения лимита.")
    else:
        text = ("🔒 Доступ ограничен.\n\n"
                "Приобретите подписку, чтобы разблокировать.")

    await callback.message.answer(text, reply_markup=subscribe_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ytdl:"))
async def ytdl_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Скачивание только аудио с YouTube."""
    _, mode, url = callback.data.split(":", 2)
    user = callback.from_user

    await set_busy(state, True)
    await callback.message.answer("⏳ Скачиваем аудио...")

    await process_youtube_or_other(callback.message, url, user.id, "youtube", state, mode)
