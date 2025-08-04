import re
from urllib.parse import urlparse, parse_qs

def clean_youtube_url(url):
    # Получаем ID видео из параметра 'v'
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    video_id = qs.get('v', [None])[0]
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    # Ищем ID в URL через регулярное выражение
    match = re.search(r'(?:v=|youtu\.be/|youtube\.com/embed/)([\w-]{11})', url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url
