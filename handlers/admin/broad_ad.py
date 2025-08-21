
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError
import asyncio
from contextlib import suppress
import logging
from db.base import get_session
from db.users import get_user_ids_without_subscription
from utils.keyboards import back_button
from config import BROADCAST_PROGRESS_UPDATE_INTERVAL, BROADCAST_PER_MESSAGE_DELAY

logger = logging.getLogger(__name__)
router = Router()

class BroadcastAdStates(StatesGroup):
    waiting_text = State()
    waiting_button_text = State()
    waiting_button_url = State()
    waiting_media = State()

def _keyboard(send_button_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Текст", callback_data="ad_broadcast:set_text"),
         InlineKeyboardButton(text="📌 Кнопка", callback_data="ad_broadcast:set_button"),
         InlineKeyboardButton(text="🎬 Медиа", callback_data="ad_broadcast:set_media")],
        [InlineKeyboardButton(text="👀 Предпросмотр", callback_data="ad_broadcast:preview")],
        [InlineKeyboardButton(text=send_button_label, callback_data="ad_broadcast:send"),
         InlineKeyboardButton(text="🚫 Стоп", callback_data="ad_broadcast:cancel")],
    ])

@router.callback_query(F.data == "ad_broadcast_start")
async def start_broadcast_ad(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await state.update_data(constructor_message_id=callback.message.message_id)
    await _edit_constructor(callback.message, state, bot)
    await callback.answer()

async def _edit_constructor(message: Message, state: FSMContext, bot: Bot):
    with suppress(TelegramAPIError):
        await message.edit_text(
            "💸 Рекламная рассылка\n\nРасскажите о новых возможностях или скидках тем, у кого нет подписки.",
            reply_markup=_keyboard("Отправить"),
            parse_mode="Markdown"
        )

@router.callback_query(F.data == "ad_broadcast:cancel")
async def cancel_broadcast_ad(callback: CallbackQuery, state: FSMContext):
    from handlers.admin.menu import get_admin_menu_keyboard
    await state.clear()
    await callback.message.edit_text("🔐 Админ-панель", reply_markup=get_admin_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "ad_broadcast:set_text")
async def set_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastAdStates.waiting_text)
    prompt = await callback.message.answer("Введите текст рекламы:")
    await state.update_data(prompt_message_id=prompt.message_id)
    await callback.answer()

@router.message(BroadcastAdStates.waiting_text)
async def process_text(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(text=message.text)
    await state.set_state(None)
    await _cleanup(message, state, bot)

@router.callback_query(F.data == "ad_broadcast:set_button")
async def set_button_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastAdStates.waiting_button_text)
    prompt = await callback.message.answer("Введите текст кнопки:")
    await state.update_data(prompt_message_id=prompt.message_id)
    await callback.answer()

@router.message(BroadcastAdStates.waiting_button_text)
async def process_button_text(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(button_text=message.text)
    await state.set_state(BroadcastAdStates.waiting_button_url)
    await _cleanup(message, state, bot)
    prompt = await message.answer("Теперь введите URL (http/https):")
    await state.update_data(prompt_message_id=prompt.message_id)

@router.message(BroadcastAdStates.waiting_button_url)
async def process_button_url(message: Message, state: FSMContext, bot: Bot):
    url = (message.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("Неверный URL. Начните с http:// или https://")
        return
    await state.update_data(button_url=url)
    await state.set_state(None)
    await _cleanup(message, state, bot)

@router.callback_query(F.data == "ad_broadcast:set_media")
async def set_media(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastAdStates.waiting_media)
    prompt = await callback.message.answer("Пришлите фото или видео для рекламы (или /skip для пропуска):")
    await state.update_data(prompt_message_id=prompt.message_id)
    await callback.answer()

@router.message(BroadcastAdStates.waiting_media)
async def process_media(message: Message, state: FSMContext, bot: Bot):
    media_id = media_type = None
    if message.photo:
        media_id, media_type = message.photo[-1].file_id, "photo"
    elif message.video:
        media_id, media_type = message.video.file_id, "video"
    elif message.text and message.text.strip() == "/skip":
        await state.update_data(media_id=None, media_type=None)
        await state.set_state(None)
        await _cleanup(message, state, bot)
        return
    else:
        await message.answer("Пожалуйста, отправьте фото или видео, либо /skip для пропуска.")
        return
    await state.update_data(media_id=media_id, media_type=media_type)
    await state.set_state(None)
    await _cleanup(message, state, bot)

@router.callback_query(F.data == "ad_broadcast:preview")
async def preview(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("text")
    if not text:
        await callback.answer("❗️ Сначала задайте текст.", show_alert=True)
        return
    markup = _make_markup(data.get("button_text"), data.get("button_url"))
    media_id, media_type = data.get("media_id"), data.get("media_type")
    if media_id and media_type == "photo":
        await callback.message.answer_photo(media_id, caption=text, reply_markup=markup)
    elif media_id and media_type == "video":
        await callback.message.answer_video(media_id, caption=text, reply_markup=markup)
    else:
        await callback.message.answer(text, reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data == "ad_broadcast:send")
async def send_broadcast_ad(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data.get("text")
    if not text:
        await callback.answer("❗️ Пустое сообщение.", show_alert=True)
        return
    await callback.message.edit_text("⏳ Рассылка началась! По завершении придёт отчёт.", reply_markup=back_button())
    asyncio.create_task(_send_task(bot, callback.from_user.id, data))
    await state.clear()
    await callback.answer()

async def _send_task(bot: Bot, admin_id: int, data: dict):
    from db.base import get_session
    from db.users import get_user_ids_without_subscription
    text = data.get("text")
    markup = _make_markup(data.get("button_text"), data.get("button_url"))
    media_id, media_type = data.get("media_id"), data.get("media_type")
    sent = failed = 0
    async with get_session() as session:
        user_ids = await get_user_ids_without_subscription(session)
    if not user_ids:
        await bot.send_message(admin_id, "❗️ Аудитория пуста. Сообщение никому не отправлено.")
        return
    total = len(user_ids)
    logger.info(f"Начинается рассылка 'ad_broadcast' для {total} пользователей.")
    progress_msg = await bot.send_message(admin_id, _render_progress_bar(0, total))
    last_update = asyncio.get_event_loop().time()
    for user_id in user_ids:
        try:
            if media_id and media_type == "photo":
                await bot.send_photo(user_id, media_id, caption=text, reply_markup=markup)
            elif media_id and media_type == "video":
                await bot.send_video(user_id, media_id, caption=text, reply_markup=markup)
            else:
                await bot.send_message(user_id, text, reply_markup=markup)
            sent += 1
        except TelegramAPIError as e:
            error_text = str(e)
            if 'Too Many Requests' in error_text or 'FLOOD_WAIT' in error_text:
                logger.error("FloodWait: превышен лимит Telegram при отправке %s: %s", user_id, error_text)
            elif 'bot was blocked by the user' in error_text:
                logger.info("BotBlocked: пользователь %s заблокировал бота", user_id)
            elif 'chat not found' in error_text:
                logger.info("ChatNotFound: чат %s не найден", user_id)
            elif 'user is deactivated' in error_text:
                logger.info("UserDeactivated: пользователь %s деактивирован", user_id)
            else:
                logger.warning("Не удалось отправить сообщение пользователю %s: %s", user_id, error_text)
            failed += 1
        except Exception as e:
            logger.error("Неизвестная ошибка при отправке пользователю %s: %s", user_id, e, exc_info=True)
            failed += 1
        now = asyncio.get_event_loop().time()
        if (sent % 100 == 0 or sent == total) or (now - last_update > BROADCAST_PROGRESS_UPDATE_INTERVAL):
            with suppress(TelegramAPIError):
                await bot.edit_message_text(
                    text=_render_progress_bar(sent, total),
                    chat_id=admin_id,
                    message_id=progress_msg.message_id
                )
            last_update = now
        await asyncio.sleep(BROADCAST_PER_MESSAGE_DELAY)
    logger.info("Рассылка 'ad_broadcast' завершена. Отправлено=%s Ошибок=%s", sent, failed)
    percent = int(sent / total * 100) if total else 0
    summary_text = (
        f"💸 [РЕКЛАМНАЯ РАССЫЛКА] Завершена!\n\n"
        f"⛔️ Без подписки: {total}\n"
        f"✅ Доставлено: {sent} ({percent}%)\n"
        f"❌ Не доставлено: {failed}"
    )
    with suppress(TelegramAPIError):
        await bot.edit_message_text(
            text=_render_progress_bar(sent, total),
            chat_id=admin_id,
            message_id=progress_msg.message_id
        )
    await bot.send_message(admin_id, summary_text, parse_mode="Markdown")

def _make_markup(button_text, button_url):
    if button_text and button_url:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=button_text, url=button_url)]])
    return None

def _render_progress_bar(sent, total, bar_length=10):
    percent = sent / total if total else 0
    filled = int(bar_length * percent)
    bar = '🟩' * filled + '⬜' * (bar_length - filled)
    return f"Прогресс: [{bar}] {int(percent*100)}% ({sent}/{total})"

async def _cleanup(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    prompt_msg_id = data.get("prompt_message_id")
    constructor_msg_id = data.get("constructor_message_id")
    with suppress(TelegramAPIError):
        if prompt_msg_id:
            await bot.delete_message(message.chat.id, prompt_msg_id)
        await message.delete()
    if constructor_msg_id:
        with suppress(TelegramAPIError):
            await bot.edit_message_text(
                text="💸 Рекламная рассылка\n\nРасскажите о новых возможностях или скидках тем, у кого нет подписки.",
                chat_id=message.chat.id,
                message_id=constructor_msg_id,
                reply_markup=_keyboard("Отправить"),
                parse_mode="Markdown"
            )
