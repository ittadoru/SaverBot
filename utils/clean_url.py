def strip_url_after_ampersand(url: str) -> str:
    """
    Возвращает url без аргументов после первого & (оставляет только до первого &).
    Например: https://youtube.com/watch?v=abc&list=xyz -> https://youtube.com/watch?v=abc
    """
    if '&' in url:
        return url.split('&', 1)[0]
    return url