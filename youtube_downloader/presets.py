from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class VideoQualityPreset:
    key: str
    label: str
    max_height: Optional[int]
    description: str


@dataclass(frozen=True)
class AudioQualityPreset:
    key: str
    label: str
    bitrate_kbps: int
    description: str


VIDEO_QUALITY_PRESETS: Tuple[VideoQualityPreset, ...] = (
    VideoQualityPreset("best", "Best available", None, "Highest quality YouTube offers."),
    VideoQualityPreset("2160", "Up to 4K (2160p)", 2160, "Keep 4K and below."),
    VideoQualityPreset("1440", "Up to 2K (1440p)", 1440, "Keep 2K and below."),
    VideoQualityPreset("1080", "Up to Full HD (1080p)", 1080, "A good balance of quality and size."),
    VideoQualityPreset("720", "Up to HD (720p)", 720, "Smaller files with solid quality."),
    VideoQualityPreset("480", "Up to SD (480p)", 480, "Compact files for quick downloads."),
)

AUDIO_QUALITY_PRESETS: Tuple[AudioQualityPreset, ...] = (
    AudioQualityPreset("320", "High (320 kbps)", 320, "Best quality MP3 output."),
    AudioQualityPreset("256", "Very good (256 kbps)", 256, "Smaller file, still high quality."),
    AudioQualityPreset("192", "Good (192 kbps)", 192, "Balanced size and quality."),
    AudioQualityPreset("128", "Economy (128 kbps)", 128, "Smallest file size."),
)

VIDEO_QUALITY_BY_KEY: Dict[str, VideoQualityPreset] = {preset.key: preset for preset in VIDEO_QUALITY_PRESETS}
VIDEO_QUALITY_BY_LABEL: Dict[str, VideoQualityPreset] = {preset.label: preset for preset in VIDEO_QUALITY_PRESETS}
AUDIO_QUALITY_BY_KEY: Dict[str, AudioQualityPreset] = {preset.key: preset for preset in AUDIO_QUALITY_PRESETS}
AUDIO_QUALITY_BY_LABEL: Dict[str, AudioQualityPreset] = {preset.label: preset for preset in AUDIO_QUALITY_PRESETS}


def build_output_template(playlist: bool) -> str:
    if playlist:
        return "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
    return "%(title)s.%(ext)s"


def video_format_selector(preset_key: str) -> str:
    preset = VIDEO_QUALITY_BY_KEY.get(preset_key, VIDEO_QUALITY_BY_KEY["best"])
    if preset.max_height is None:
        return "bestvideo+bestaudio/best"
    return f"bestvideo[height<={preset.max_height}]+bestaudio/best[height<={preset.max_height}]"


def audio_postprocessors(preset_key: str) -> List[Dict[str, str]]:
    preset = AUDIO_QUALITY_BY_KEY.get(preset_key, AUDIO_QUALITY_BY_KEY["320"])
    return [
        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": str(preset.bitrate_kbps)},
        {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
        {"key": "EmbedThumbnail"},
        {"key": "FFmpegMetadata"},
    ]


def video_labels() -> List[str]:
    return [preset.label for preset in VIDEO_QUALITY_PRESETS]


def audio_labels() -> List[str]:
    return [preset.label for preset in AUDIO_QUALITY_PRESETS]


def video_preset_from_label(label: str) -> VideoQualityPreset:
    return VIDEO_QUALITY_BY_LABEL.get(label, VIDEO_QUALITY_PRESETS[0])


def audio_preset_from_label(label: str) -> AudioQualityPreset:
    return AUDIO_QUALITY_BY_LABEL.get(label, AUDIO_QUALITY_PRESETS[0])
