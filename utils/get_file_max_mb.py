from config import DOWNLOAD_FILE_LIMIT


async def get_max_filesize_mb(level: int, sub: bool) -> int:
    """Определение максимального размера файла в зависимости от уровня и подписки."""

    if sub:
        return DOWNLOAD_FILE_LIMIT * 10
    
    if level == 1:
        return DOWNLOAD_FILE_LIMIT
    elif level == 2:
        return DOWNLOAD_FILE_LIMIT * 2
    elif level == 3:
        return DOWNLOAD_FILE_LIMIT * 4
    else:
        return DOWNLOAD_FILE_LIMIT * 10