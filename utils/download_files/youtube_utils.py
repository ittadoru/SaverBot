from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import YOUTUBE_MAX_DURATION_SECONDS
from db.base import get_session
from db.tokens import get_token_snapshot
from services.youtube import YTDLPDownloader
from utils.token_policy import YOUTUBE_QUALITY_ORDER, format_duration, get_youtube_price


QUALITY_LABELS = {
    "low": "Низкое",
    "medium": "Среднее",
    "high": "Высокое",
}


def _currency_label(currency: str) -> str:
    return "T" if currency == "token" else "TX"


def _parse_resolution(fmt: dict) -> int | None:
    res = fmt.get("res")
    if not res or not str(res).endswith("p"):
        return None
    try:
        return int(str(res).replace("p", ""))
    except ValueError:
        return None


def _pick_best_itag_for_resolution(formats: list[dict], resolution: int) -> int | None:
    candidates: list[dict] = []
    for fmt in formats:
        if _parse_resolution(fmt) != resolution:
            continue
        candidates.append(fmt)

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (
            bool(x.get("progressive")),
            int(x.get("filesize") or 0),
        ),
        reverse=True,
    )
    return int(candidates[0]["itag"])


def _build_resolution_itags(formats: list[dict]) -> dict[int, int]:
    resolutions = sorted({_parse_resolution(fmt) for fmt in formats if _parse_resolution(fmt) is not None})
    result: dict[int, int] = {}
    for res in resolutions:
        itag = _pick_best_itag_for_resolution(formats, res)
        if itag is not None:
            result[res] = itag
    return result


def _pick_low(res_to_itag: dict[int, int]) -> tuple[int, int] | None:
    if not res_to_itag:
        return None
    if 360 in res_to_itag:
        return res_to_itag[360], 360

    below_360 = sorted(res for res in res_to_itag if res < 360)
    if below_360:
        target = below_360[0]
        return res_to_itag[target], target

    return None


def _pick_medium(res_to_itag: dict[int, int]) -> tuple[int, int] | None:
    if 720 in res_to_itag:
        return res_to_itag[720], 720
    if 480 in res_to_itag:
        return res_to_itag[480], 480
    return None


def _pick_high(res_to_itag: dict[int, int]) -> tuple[int, int] | None:
    if 1440 in res_to_itag:
        return res_to_itag[1440], 1440
    if 1080 in res_to_itag:
        return res_to_itag[1080], 1080
    return None


def _pick_itag_for_quality(formats: list[dict], quality: str) -> tuple[int, int] | None:
    res_to_itag = _build_resolution_itags(formats)
    if quality == "low":
        return _pick_low(res_to_itag)
    if quality == "medium":
        return _pick_medium(res_to_itag)
    if quality == "high":
        return _pick_high(res_to_itag)
    return None


async def prepare_youtube_menu(url: str, user_id: int):
    """
    Return (keyboard, caption, preview, state_payload) for YouTube options.
    """
    downloader = YTDLPDownloader()
    info = await downloader.get_available_video_options(url)
    preview = info["thumbnail_url"]
    duration_seconds = int(info.get("duration_seconds") or 0)
    formats = info.get("formats", [])

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
        pick = _pick_itag_for_quality(formats, quality)
        price = get_youtube_price(quality, duration_seconds)
        if pick is None or price is None:
            continue

        itag, actual_res = pick
        currency, amount = price
        available_balance = snapshot.total_tokens if currency == "token" else snapshot.token_x
        affordable = available_balance >= amount
        cb = f"ytopt:{quality}" if affordable else "disabled"
        icon = "⚡️" if affordable else "🔒"
        quality_label = QUALITY_LABELS[quality]
        text = f"{icon} {quality_label} · {amount}{_currency_label(currency)}"

        options_payload[quality] = {
            "itag": itag,
            "currency": currency,
            "cost": amount,
            "actual_res": actual_res,
        }
        lines.append(f"{icon} {quality_label}: {amount} {_currency_label(currency)}")

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
            "actual_res": None,
        }
        lines.append(f"{icon} Аудио: {amount} {_currency_label(currency)}")

    if not options_payload:
        rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="start")])
        lines.append("❌ Для этого видео нет доступных форматов.")

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
