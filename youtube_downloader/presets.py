from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class VideoQualityPreset:
    key: str
    label: str
    max_height: int | None
    description: str


@dataclass(frozen=True)
class AudioQualityPreset:
    key: str
    label: str
    bitrate_kbps: int
    description: str


@dataclass(frozen=True)
class AudioFormatPreset:
    key: str
    label: str
    supports_thumbnail: bool
    description: str


@dataclass(frozen=True)
class VideoContainerPreset:
    key: str
    label: str
    supports_thumbnail: bool
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
    AudioQualityPreset("320", "High (320 kbps)", 320, "Best quality output."),
    AudioQualityPreset("256", "Very good (256 kbps)", 256, "Smaller file, still high quality."),
    AudioQualityPreset("192", "Good (192 kbps)", 192, "Balanced size and quality."),
    AudioQualityPreset("128", "Economy (128 kbps)", 128, "Smallest file size."),
)

AUDIO_FORMAT_PRESETS: Tuple[AudioFormatPreset, ...] = (
    AudioFormatPreset("mp3", "MP3", True, "Plays on every device, embeds cover art."),
    AudioFormatPreset("m4a", "M4A (AAC)", True, "Better quality per bit, Apple friendly."),
    AudioFormatPreset("opus", "Opus", True, "Modern and very efficient."),
    AudioFormatPreset("flac", "FLAC", True, "Lossless, large files."),
    AudioFormatPreset("wav", "WAV", False, "Uncompressed, no cover art support."),
)

VIDEO_CONTAINER_PRESETS: Tuple[VideoContainerPreset, ...] = (
    VideoContainerPreset("mp4", "MP4", True, "Works everywhere, supports cover art and subtitles."),
    VideoContainerPreset("mkv", "MKV", True, "Flexible container, supports cover art and subtitles."),
)

SPONSORBLOCK_CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ("sponsor", "Sponsor segments"),
    ("selfpromo", "Unpaid promotion"),
    ("interaction", "Interaction reminder"),
    ("intro", "Intro animation"),
    ("outro", "Endcards / credits"),
    ("preview", "Preview / recap"),
    ("music_offtopic", "Non-music section"),
    ("filler", "Filler tangent"),
)

SUBTITLE_LANGUAGES: Tuple[Tuple[str, str], ...] = (
    ("en", "English"),
    ("ar", "Arabic"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("tr", "Turkish"),
    ("id", "Indonesian"),
    ("pt", "Portuguese"),
    ("hi", "Hindi"),
    ("ja", "Japanese"),
)

VIDEO_QUALITY_BY_KEY: Dict[str, VideoQualityPreset] = {preset.key: preset for preset in VIDEO_QUALITY_PRESETS}
VIDEO_QUALITY_BY_LABEL: Dict[str, VideoQualityPreset] = {preset.label: preset for preset in VIDEO_QUALITY_PRESETS}
AUDIO_QUALITY_BY_KEY: Dict[str, AudioQualityPreset] = {preset.key: preset for preset in AUDIO_QUALITY_PRESETS}
AUDIO_QUALITY_BY_LABEL: Dict[str, AudioQualityPreset] = {preset.label: preset for preset in AUDIO_QUALITY_PRESETS}
AUDIO_FORMAT_BY_KEY: Dict[str, AudioFormatPreset] = {preset.key: preset for preset in AUDIO_FORMAT_PRESETS}
AUDIO_FORMAT_BY_LABEL: Dict[str, AudioFormatPreset] = {preset.label: preset for preset in AUDIO_FORMAT_PRESETS}
VIDEO_CONTAINER_BY_KEY: Dict[str, VideoContainerPreset] = {preset.key: preset for preset in VIDEO_CONTAINER_PRESETS}
VIDEO_CONTAINER_BY_LABEL: Dict[str, VideoContainerPreset] = {preset.label: preset for preset in VIDEO_CONTAINER_PRESETS}


def build_output_template(playlist: bool) -> str:
    if playlist:
        return "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
    return "%(title)s.%(ext)s"


def video_format_selector(preset_key: str) -> str:
    preset = VIDEO_QUALITY_BY_KEY.get(preset_key, VIDEO_QUALITY_BY_KEY["best"])
    if preset.max_height is None:
        return "bestvideo+bestaudio/best"
    return f"bestvideo[height<={preset.max_height}]+bestaudio/best[height<={preset.max_height}]"


def audio_postprocessors(
    audio_format: str,
    bitrate_kbps: int,
    embed_thumbnail: bool = True,
    embed_metadata: bool = True,
) -> List[Dict[str, object]]:
    preset = AUDIO_FORMAT_BY_KEY.get(audio_format, AUDIO_FORMAT_BY_KEY["mp3"])
    postprocessors: List[Dict[str, object]] = [
        {"key": "FFmpegExtractAudio", "preferredcodec": preset.key, "preferredquality": str(bitrate_kbps)},
    ]
    if preset.supports_thumbnail and embed_thumbnail:
        postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    if embed_metadata:
        postprocessors.append({"key": "FFmpegMetadata"})
    return postprocessors


def video_postprocessors(
    video_container: str,
    embed_thumbnail: bool = True,
    embed_metadata: bool = True,
    embed_subtitles: bool = False,
) -> List[Dict[str, object]]:
    container = VIDEO_CONTAINER_BY_KEY.get(video_container, VIDEO_CONTAINER_BY_KEY["mp4"])
    postprocessors: List[Dict[str, object]] = []

    if embed_subtitles and container.key in ("mp4", "mkv", "webm"):
        postprocessors.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})

    if container.supports_thumbnail and embed_thumbnail:
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    if embed_metadata:
        postprocessors.append({"key": "FFmpegMetadata"})
    return postprocessors


def sponsorblock_postprocessors(categories: Iterable[str]) -> List[Dict[str, object]]:
    selected = {str(category) for category in categories if category}
    if not selected:
        return []
    return [
        {"key": "SponsorBlock", "categories": selected, "when": "after_filter"},
        {
            "key": "ModifyChapters",
            "remove_sponsor_segments": selected,
            "remove_chapters_patterns": [],
            "remove_ranges": [],
            "sponsorblock_chapter_title": "",
            "force_keyframes": False,
        },
    ]


def playlist_items_string(indexes: Iterable[int]) -> str:
    unique = sorted({int(index) for index in indexes if int(index) > 0})
    return ",".join(str(index) for index in unique)


def video_labels() -> List[str]:
    return [preset.label for preset in VIDEO_QUALITY_PRESETS]


def audio_labels() -> List[str]:
    return [preset.label for preset in AUDIO_QUALITY_PRESETS]


def audio_format_labels() -> List[str]:
    return [preset.label for preset in AUDIO_FORMAT_PRESETS]


def video_container_labels() -> List[str]:
    return [preset.label for preset in VIDEO_CONTAINER_PRESETS]


def sponsorblock_labels() -> List[str]:
    return [label for _, label in SPONSORBLOCK_CATEGORIES]


def subtitle_language_labels() -> List[str]:
    return [label for _, label in SUBTITLE_LANGUAGES]


def subtitle_language_codes(labels: Sequence[str]) -> Tuple[str, ...]:
    by_label = dict(SUBTITLE_LANGUAGES)
    return tuple(by_label[label] for label in labels if label in by_label)


def sponsorblock_keys(labels: Sequence[str]) -> Tuple[str, ...]:
    by_label = dict((label, key) for key, label in SPONSORBLOCK_CATEGORIES)
    return tuple(by_label[label] for label in labels if label in by_label)


def video_preset_from_label(label: str) -> VideoQualityPreset:
    return VIDEO_QUALITY_BY_LABEL.get(label, VIDEO_QUALITY_PRESETS[0])


def audio_preset_from_label(label: str) -> AudioQualityPreset:
    return AUDIO_QUALITY_BY_LABEL.get(label, AUDIO_QUALITY_PRESETS[0])


def audio_format_from_label(label: str) -> AudioFormatPreset:
    return AUDIO_FORMAT_BY_LABEL.get(label, AUDIO_FORMAT_PRESETS[0])


def video_container_from_label(label: str) -> VideoContainerPreset:
    return VIDEO_CONTAINER_BY_LABEL.get(label, VIDEO_CONTAINER_PRESETS[0])
