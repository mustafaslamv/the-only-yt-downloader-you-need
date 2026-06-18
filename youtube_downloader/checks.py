from shutil import which


def ffmpeg_available() -> bool:
    return which("ffmpeg") is not None
