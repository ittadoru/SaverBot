from moviepy import VideoFileClip


def get_video_resolution(path: str) -> tuple[int, int]:
    """
    Получает разрешение видеофайла.
    """
    with VideoFileClip(path) as clip:
        return clip.w, clip.h
