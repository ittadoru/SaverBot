import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from utils.download_files.clean_url import strip_url_after_ampersand
from utils.platform_detect import detect_platform
from utils.download_files.download_manager import (
    is_busy, set_busy, check_download_permissions, process_youtube_or_other
)
from utils.download_files.youtube_utils import prepare_youtube_menu

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
        platform = detect_platform(url)
        # Проверка лимитов и обязательных каналов
        can_download, reason = await check_download_permissions(user.id, platform, message.bot)
        if not can_download:
            return await message.answer(reason, parse_mode="HTML")

        if platform == "youtube":
            keyboard, caption, preview, yt_payload = await prepare_youtube_menu(url, user.id)
            await state.update_data(
                {
                    "yt_url": url,
                    "yt_duration_seconds": yt_payload.get("duration_seconds"),
                    "yt_options": yt_payload.get("options", {}),
                }
            )
            return await message.answer_photo(
                photo=preview,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="HTML",
            )

        await process_youtube_or_other(message, url, user.id, platform, state)
    except Exception as e:
        logger.error(f"❌ Ошибка в download_handler: {e}", exc_info=True)
        await message.answer("❗️ Ошибка при скачивании, попробуйте позже.")
    finally:
        await set_busy(state, False)
        await wait_message.delete()

@router.callback_query(lambda c: c.data.startswith("ytopt:"))
async def ytopt_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Выбор YouTube-качества или аудио."""
    if await is_busy(state):
        await callback.answer("⏳ Уже выполняется другая загрузка.", show_alert=True)
        return
    await set_busy(state, True)
    try:
        _, quality = callback.data.split(":", 1)
        await callback.message.answer("⏳ Скачиваем, подождите пару минут...")
        data = await state.get_data()
        url = data.get("yt_url")
        user = callback.from_user
        await process_youtube_or_other(callback.message, url, user.id, "youtube", state, quality)
    except Exception as e:
        logger.error(f"❌ Ошибка в ytopt_callback_handler: {e}", exc_info=True)
        await callback.answer("❗️ Ошибка при скачивании, попробуйте позже.", show_alert=True)
    finally:
        await set_busy(state, False)

@router.callback_query(lambda c: c.data == "disabled")
async def yt_disabled_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработка нажатия на недоступную кнопку качества."""
    text = (
        "🔒 Этот вариант сейчас недоступен.\n\n"
        "Проверь баланс токенов/наличие формата для этого видео."
    )
    await callback.answer(text, show_alert=True)
