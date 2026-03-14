from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import YOUTUBE_MAX_DURATION_SECONDS
from db.base import get_session
from db.tokens import get_token_snapshot
from services.youtube import YTDLPDownloader
from utils.token_policy import (
    YOUTUBE_QUALITY_ORDER,
    format_duration,
    get_youtube_price,
)


QUALITY_TO_RESOLUTION = {
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "1440p": 1440,
    "4k": 2160,
}


def _pick_itag_for_resolution(formats: list[dict], resolution: int) -> int | None:
    candidates: list[dict] = []
    for fmt in formats:
        res = fmt.get("res")
        if not res or not str(res).endswith("p"):
            continue
        try:
            res_int = int(str(res).replace("p", ""))
        except ValueError:
            continue
        if res_int == resolution:
            candidates.append(fmt)

    if not candidates:
        return None

    # Prefer progressive streams, then larger filesize.
    candidates.sort(
        key=lambda x: (
            bool(x.get("progressive")),
            int(x.get("filesize") or 0),
        ),
        reverse=True,
    )
    return int(candidates[0]["itag"])


def _currency_label(currency: str) -> str:
    return "T" if currency == "token" else "TX"


async def prepare_youtube_menu(url: str, user_id: int):
    """
    Return (keyboard, caption, preview, state_payload) for YouTube options.
    """
    downloader = YTDLPDownloader()
    info = await downloader.get_available_video_options(url)
    preview = info["thumbnail_url"]
    duration_seconds = int(info.get("duration_seconds") or 0)

    async with get_session() as session:
        snapshot = await get_token_snapshot(session, user_id, refresh_daily=True)
        await session.commit()

    lines = [
        f"<b>🎬 {info['title']}</b>",
        f"⏱ Длительность: <b>{format_duration(duration_seconds)}</b>",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    options_payload: dict[str, dict] = {}

    if duration_seconds >= YOUTUBE_MAX_DURATION_SECONDS:
        lines.append("❌ Видео длиннее 3 часов недоступны для скачивания.")
        rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="start")])
        return (
            InlineKeyboardMarkup(inline_keyboard=rows),
            "\n".join(lines),
            preview,
            {"duration_seconds": duration_seconds, "options": options_payload},
        )

    for quality in YOUTUBE_QUALITY_ORDER:
        target_res = QUALITY_TO_RESOLUTION[quality]
        itag = _pick_itag_for_resolution(info["formats"], target_res)
        price = get_youtube_price(quality, duration_seconds)

        if itag is None or price is None:
            text = f"🔒 {quality}"
            cb = "disabled"
        else:
            currency, amount = price
            available_balance = snapshot.total_tokens if currency == "token" else snapshot.token_x
            affordable = available_balance >= amount
            cb = f"ytopt:{quality}" if affordable else "disabled"
            icon = "⚡️" if affordable else "🔒"
            text = f"{icon} {quality} · {amount}{_currency_label(currency)}"
            options_payload[quality] = {
                "itag": itag,
                "currency": currency,
                "cost": amount,
            }
            lines.append(f"{icon} {quality}: {amount} {_currency_label(currency)}")

        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    audio_price = get_youtube_price("audio", duration_seconds)
    if audio_price:
        currency, amount = audio_price
        balance = snapshot.total_tokens if currency == "token" else snapshot.token_x
        affordable = balance >= amount
        icon = "⚡️" if affordable else "🔒"
        callback_data = "ytopt:audio" if affordable else "disabled"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} 🎧 Аудио · {amount}{_currency_label(currency)}",
                    callback_data=callback_data,
                )
            ]
        )
        options_payload["audio"] = {
            "itag": None,
            "currency": currency,
            "cost": amount,
        }
        lines.append(f"{icon} Аудио: {amount} {_currency_label(currency)}")

    lines.append(
        "\n<b>Баланс:</b> "
        f"токены <b>{snapshot.total_tokens}</b> "
        f"(ежедневные {snapshot.daily_tokens}, бонусные {snapshot.bonus_tokens}), "
        f"tokenX <b>{snapshot.token_x}</b>"
    )
    lines.append("<i>Выбери качество. Недоступные кнопки отмечены 🔒.</i>")

    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    payload = {"duration_seconds": duration_seconds, "options": options_payload}
    return keyboard, "\n".join(lines), preview, payload
