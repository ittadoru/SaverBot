from moviepy import VideoFileClip


def get_video_resolution(path: str) -> tuple[int, int]:
    """
    Получает разрешение видеофайла.
    """
    clip = VideoFileClip(path)
    return clip.w, clip.h
