"""User token actions: balances, exchange and daily Tiktok/Insta limit reset."""

from __future__ import annotations

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    SOCIAL_DAILY_LIMIT,
    SOCIAL_RESET_TOKEN_COST,
    SOCIAL_RESET_TOKEN_X_COST,
    TOKEN_X_TO_TOKEN_RATE,
)
from db.base import get_session
from db.downloads import get_total_downloads
from db.tokens import (
    exchange_token_x_to_tokens,
    get_daily_social_usage,
    get_token_snapshot,
    reset_daily_social_usage,
    spend_token_x,
    spend_tokens,
)


router = Router()


def _tokens_keyboard() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"💱 Обменять 1 tokenX → {TOKEN_X_TO_TOKEN_RATE} токенов",
        callback_data="exchange_tokenx_1",
    )
    builder.button(
        text=f"♻️ Сброс Tiktok/Insta за {SOCIAL_RESET_TOKEN_COST} токенов",
        callback_data="social_reset:token",
    )
    builder.button(
        text=f"♻️ Сброс Tiktok/Insta за {SOCIAL_RESET_TOKEN_X_COST} tokenX",
        callback_data="social_reset:tokenx",
    )
    builder.button(text="⬅️ Назад", callback_data="start")
    builder.adjust(1)
    return builder.as_markup()


async def build_profile_block(user_id: int) -> str:
    async with get_session() as session:
        snapshot = await get_token_snapshot(session, user_id, refresh_daily=True)
        social_used = await get_daily_social_usage(session, user_id)
        total_downloads = await get_total_downloads(session, user_id)
        await session.commit()

    social_left = max(0, SOCIAL_DAILY_LIMIT - social_used)
    return (
        "<b>👤 Твой профиль:</b>\n"
        f"<b>•</b> Токены: <b>{snapshot.total_tokens}</b> "
        f"(ежедневные: {snapshot.daily_tokens}, бонусные: {snapshot.bonus_tokens})\n"
        f"<b>•</b> tokenX: <b>{snapshot.token_x}</b>\n"
        f"<b>•</b> Осталось Tiktok/Insta сегодня: <b>{social_left}/{SOCIAL_DAILY_LIMIT}</b>\n"
        f"<b>•</b> Всего скачиваний: <b>{total_downloads}</b>"
    )


@router.callback_query(F.data == "tokens_menu")
async def tokens_menu(callback: types.CallbackQuery) -> None:
    profile = await build_profile_block(callback.from_user.id)
    text = (
        "<b>💱 Токены и лимиты</b>\n\n"
        f"{profile}\n\n"
        "Здесь можно обменять tokenX и сбросить дневной лимит Tiktok/Insta."
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_tokens_keyboard())
    await callback.answer()


@router.callback_query(F.data == "exchange_tokenx_1")
async def exchange_tokenx_one(callback: types.CallbackQuery) -> None:
    user_id = callback.from_user.id
    async with get_session() as session:
        ok, snapshot = await exchange_token_x_to_tokens(
            session=session,
            user_id=user_id,
            token_x_amount=1,
            rate=TOKEN_X_TO_TOKEN_RATE,
        )
        await session.commit()

    if ok:
        await callback.answer(
            f"✅ Обмен выполнен. Токены: {snapshot.total_tokens}, tokenX: {snapshot.token_x}",
            show_alert=True,
        )
    else:
        await callback.answer("❗️Недостаточно tokenX для обмена.", show_alert=True)


@router.callback_query(F.data.startswith("social_reset:"))
async def social_reset_limit(callback: types.CallbackQuery) -> None:
    mode = (callback.data or "").split(":", 1)[1]
    user_id = callback.from_user.id

    async with get_session() as session:
        used = await get_daily_social_usage(session, user_id)
        if used < SOCIAL_DAILY_LIMIT:
            await session.commit()
            await callback.answer("Лимит ещё не исчерпан, сброс не нужен.", show_alert=True)
            return

        if mode == "token":
            paid, _ = await spend_tokens(session, user_id, SOCIAL_RESET_TOKEN_COST)
            if not paid:
                await session.commit()
                await callback.answer("❗️Недостаточно обычных токенов.", show_alert=True)
                return
        elif mode == "tokenx":
            paid, _ = await spend_token_x(session, user_id, SOCIAL_RESET_TOKEN_X_COST)
            if not paid:
                await session.commit()
                await callback.answer("❗️Недостаточно tokenX.", show_alert=True)
                return
        else:
            await session.commit()
            await callback.answer("Неизвестный способ сброса.", show_alert=True)
            return

        await reset_daily_social_usage(session, user_id)
        await session.commit()

    await callback.answer("✅ Лимит Tiktok/Insta сброшен. Можно скачивать снова.", show_alert=True)
