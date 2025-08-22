"""Поддержка (пользователь): создание тикета, диалог и закрытие."""

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import SUPPORT_GROUP_ID
from db.base import get_session
from db.support import SupportTicket, close_ticket, create_ticket, get_open_ticket
from db.users import add_or_update_user
from sqlalchemy import select
from states.support import Support


logger = logging.getLogger(__name__)

router = Router()

cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_support")]]
)


@router.callback_query(F.data == "help")
@router.message(F.text.lower() == "/help")
async def start_support_handler(event, state: FSMContext) -> None:
    """Старт / помощь: создаёт или переиспользует персональный тикет пользователя."""
    if isinstance(event, CallbackQuery):
        user = event.from_user
        answer_func = event.message.answer
        done_func = event.answer
    else:
        user = event.from_user
        answer_func = event.answer
        done_func = lambda *a, **kw: None
    user_id = user.id
    async with get_session() as session:
        # гарантируем запись пользователя
        await add_or_update_user(session, user.id, user.first_name, user.username)
        # находим последний тикет (любое состояние)
        result = await session.execute(
            select(SupportTicket).where(SupportTicket.user_id == user_id).order_by(SupportTicket.created_at.desc())
        )
        ticket: Optional[SupportTicket] = result.scalars().first()

        if ticket and ticket.is_closed == 0:
            # активный есть — просто переводим в диалог
            await state.set_state(Support.in_dialog)
            await answer_func(
                "У вас уже открыт диалог с поддержкой. Напишите сообщение."
            )
            await done_func()
            return
        elif ticket and ticket.is_closed == 1:
            # переоткрываем существующий
            ticket.is_closed = 0
            renamed = False
            # если username изменился — обновим stored и постараемся переименовать тему
            if ticket.username != user.username:
                ticket.username = user.username
                try:
                    # попытка переименовать тему (если доступно)
                    new_name = f"Тикет @{user.username}" if user.username else f"Тикет {user.id}"
                    await event.bot.edit_forum_topic(
                        chat_id=SUPPORT_GROUP_ID,
                        message_thread_id=ticket.topic_id,
                        name=new_name[:128],  # ограничение TG
                    )
                    renamed = True
                except Exception:  # noqa: BLE001
                    pass
            await session.commit()
            await state.set_state(Support.waiting_for_question)
            text = "Диалог с поддержкой переоткрыт. Опишите проблему одним сообщением." + (" (Название обновлено)" if renamed else "")
            await answer_func(text, reply_markup=cancel_kb)
            await done_func()
            return

    # Нет тикета — попросим первое сообщение
    await state.set_state(Support.waiting_for_question)
    await answer_func(
        "Опишите вашу проблему или вопрос одним сообщением. "
        "Я передам его в поддержку. Вы можете отправить текст, фото, видео или документ.",
        reply_markup=cancel_kb
    )
    await done_func()


@router.message(Support.waiting_for_question)
async def create_ticket_handler(message: Message, state: FSMContext) -> None:
    """
    Создает тикет после получения первого сообщения от пользователя.
    Пересылает вопрос в группу поддержки и уведомляет пользователя.
    """
    await state.clear()
    user = message.from_user
    user_info = (
        f"👤 <b>Пользователь:</b> {user.full_name}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Username:</b> {f'@{user.username}' if user.username else 'не указан'}"
    )

    try:
        async with get_session() as session:
            # Ещё раз возьмём (на случай гонки) последний тикет
            result = await session.execute(
                select(SupportTicket).where(SupportTicket.user_id == user.id).order_by(SupportTicket.created_at.desc())
            )
            ticket: Optional[SupportTicket] = result.scalars().first()

            if ticket and ticket.is_closed == 0:
                topic_id = ticket.topic_id
            elif ticket and ticket.is_closed == 1:
                ticket.is_closed = 0
                topic_id = ticket.topic_id
                # попытка переименовать при изменении username
                if ticket.username != user.username:
                    ticket.username = user.username
                    try:
                        new_name = f"Тикет @{user.username}" if user.username else f"Тикет {user.id}"
                        await message.bot.edit_forum_topic(
                            chat_id=SUPPORT_GROUP_ID,
                            message_thread_id=topic_id,
                            name=new_name[:128],
                        )
                    except Exception:  # noqa: BLE001
                        pass
                await session.commit()
            else:
                # создаём новую тему и тикет
                topic = await message.bot.create_forum_topic(
                    chat_id=SUPPORT_GROUP_ID,
                    name=(f"Тикет @{user.username}" if user.username else f"Тикет {user.id}")[:128],
                )
                topic_id = topic.message_thread_id
                await add_or_update_user(session, user.id, user.first_name, user.username)
                await create_ticket(
                    session,
                    user_id=user.id,
                    username=user.username,
                    topic_id=topic_id,
                )

        # Отправляем инфо и сообщение пользователя в тему
        await message.bot.send_message(
            SUPPORT_GROUP_ID, user_info, message_thread_id=topic_id
        )
        await message.copy_to(chat_id=SUPPORT_GROUP_ID, message_thread_id=topic_id)

        await message.answer(
            "✅ Ваше сообщение передано в поддержку. Ожидайте ответа.\n\n"
            "Чтобы завершить диалог, отправьте команду /stop."
        )
        await state.set_state(Support.in_dialog)
        logger.info("📩 [SUPPORT] Пользователь %d создал тикет в теме %d (reuse/create)", user.id, topic_id)
    except Exception as e:
        logger.error("❌ [SUPPORT] Не удалось обработать тикет пользователя %d: %s", user.id, e)
        await message.answer("❗️ Ошибка при обработке обращения. Попробуйте позже.")


@router.message(Support.in_dialog, F.text.lower().in_(["/stop", "стоп", "закрыть"]))
@router.callback_query(Support.in_dialog, F.data == "cancel_support")
async def close_ticket_by_user_handler(event, state: FSMContext) -> None:
    """
    Закрывает тикет по команде или кнопке от пользователя.
    """
    if isinstance(event, Message):
        user_id = event.from_user.id
    else:
        user_id = event.from_user.id
    """
    Закрывает тикет по команде от пользователя.
    """
    async with get_session() as session:
        ticket: Optional[SupportTicket] = await get_open_ticket(session, user_id)
        if not ticket:
            if isinstance(event, Message):
                await event.answer("У вас нет активного диалога с поддержкой.")
            else:
                await event.message.answer("У вас нет активного диалога с поддержкой.")
            await state.clear()
            return

        await close_ticket(session, user_id)
        await state.clear()

        if isinstance(event, Message):
            await event.answer("Диалог с поддержкой завершён. Вы снова можете пользоваться ботом.")
        else:
            await event.message.edit_text("Диалог с поддержкой завершён. Вы снова можете пользоваться ботом.")
            await event.answer()
        try:
            await event.bot.send_message(
                SUPPORT_GROUP_ID,
                "❌ Пользователь завершил диалог.",
                message_thread_id=ticket.topic_id,
            )
        except Exception as e:
            logger.error(
                "❌ [SUPPORT] Не удалось уведомить группу поддержки о закрытии тикета %d: %s",
                ticket.topic_id,
                e,
            )
        logger.info("✅ [SUPPORT] Пользователь %d закрыл свой тикет (тема %d)", user_id, ticket.topic_id)


@router.message(Support.in_dialog)
async def forward_to_support_handler(message: Message) -> None:
    """
    Пересылает последующие сообщения пользователя в соответствующую тему поддержки.
    """
    user_id = message.from_user.id
    async with get_session() as session:
        ticket: Optional[SupportTicket] = await get_open_ticket(session, user_id)
        if not ticket:
            await message.answer("Ваш диалог с поддержкой уже закрыт. Чтобы начать новый, нажмите /help.")
            return

        try:
            await message.copy_to(
                chat_id=SUPPORT_GROUP_ID, message_thread_id=ticket.topic_id
            )
        except Exception as e:
            logger.error(
                "❌ [SUPPORT] Не удалось переслать сообщение от пользователя %d в тикет %d: %s",
                user_id,
                ticket.topic_id,
                e,
            )
            await message.answer("❗️ Не удалось доставить ваше сообщение. Попробуйте позже.")

@router.callback_query(Support.waiting_for_question, F.data == "cancel_support")
async def cancel_support_before_ticket_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Позволяет отменить обращение до создания тикета (на этапе ожидания вопроса).
    """
    await state.clear()
    await callback.message.edit_text("Обращение отменено. Если потребуется помощь — просто нажмите 'Помощь' снова.")
    await callback.answer()