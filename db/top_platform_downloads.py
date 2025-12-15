from sqlalchemy import select, func
from db.downloads import DownloadLink
from utils.platform_detect import detect_platform


PLATFORMS = ["youtube", "tiktok", "instagram"]

async def get_top_platform_downloads(session, limit=5):
    """
    Возвращает топ скачиваний по платформам.
    Возвращает dict: {platform: [(url, count), ...]}
    """
    result = {p: [] for p in PLATFORMS}
    for platform in PLATFORMS:
        # Фильтруем по платформе через detect_platform
        q = select(DownloadLink.url, func.count(DownloadLink.url)) \
            .group_by(DownloadLink.url)
        rows = (await session.execute(q)).all()
        # Оставляем только нужную платформу
        filtered = [(url, cnt) for url, cnt in rows if detect_platform(url) == platform]
        filtered.sort(key=lambda x: x[1], reverse=True)
        result[platform] = filtered[:limit]
    return result
