from __future__ import annotations

import importlib
from typing import Callable, List, Optional

from .checks import ffmpeg_available
from .models import DownloadMode, DownloadProgress, DownloadRequest, PlaylistEntry, ProbeKind, ProbeResult
from .presets import (
    AUDIO_QUALITY_BY_KEY,
    VIDEO_QUALITY_BY_KEY,
    audio_postprocessors,
    build_output_template,
    sponsorblock_postprocessors,
    video_format_selector,
    video_postprocessors,
)

ProgressCallback = Callable[[DownloadProgress], None]
ShouldStop = Callable[[], bool]


def extraction_options() -> dict:
    """Options that keep YouTube extraction working as the site changes."""
    return {
        "js_runtimes": {"deno": {}, "node": {}},
        "remote_components": ["ejs:github"],
    }


class DownloadCancelled(Exception):
    """Raised when the user asks to stop an active download."""


class YouTubeDownloader:
    def probe(self, url: str, single_video: bool = False) -> ProbeResult:
        """Read metadata for a URL without downloading anything."""
        yt_dlp = self._load_yt_dlp()
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "ignoreerrors": True,
            "noplaylist": bool(single_video),
            **extraction_options(),
        }

        with yt_dlp.YoutubeDL(options) as handle:
            info = handle.extract_info(url, download=False, process=True)

        if not info:
            raise RuntimeError("Could not read that URL. Check the link and try again.")

        info_type = str(info.get("_type") or "")
        if info_type in ("playlist", "multi_video"):
            raw_entries = list(info.get("entries") or [])
            return ProbeResult(
                kind=ProbeKind.PLAYLIST,
                url=url,
                title=str(info.get("title") or "Playlist"),
                uploader=str(info.get("uploader") or info.get("channel")) if (info.get("uploader") or info.get("channel")) else None,
                thumbnail_url=self._thumbnail_of(info),
                entry_count=len(raw_entries),
                entries=self._entries_of(raw_entries),
            )

        return ProbeResult(
            kind=ProbeKind.VIDEO,
            url=url,
            title=str(info.get("title") or "Video"),
            uploader=str(info.get("uploader") or info.get("channel")) if (info.get("uploader") or info.get("channel")) else None,
            duration=int(info["duration"]) if isinstance(info.get("duration"), (int, float)) else None,
            thumbnail_url=self._thumbnail_of(info),
            entry_count=1,
        )

    @staticmethod
    def _thumbnail_of(info: dict) -> Optional[str]:
        thumbnail = info.get("thumbnail")
        if thumbnail:
            return str(thumbnail)
        thumbnails = info.get("thumbnails") or []
        if thumbnails and isinstance(thumbnails[-1], dict) and thumbnails[-1].get("url"):
            return str(thumbnails[-1]["url"])
        return None

    @staticmethod
    def _entries_of(raw_entries: list) -> tuple:
        entries: List[PlaylistEntry] = []
        for position, raw in enumerate(raw_entries, start=1):
            if not isinstance(raw, dict):
                continue
            entry_id = str(raw.get("id") or "")
            raw_url = str(raw.get("url") or raw.get("webpage_url") or "")
            if raw_url and not raw_url.startswith(("http://", "https://")):
                raw_url = f"https://www.youtube.com/watch?v={raw_url}"
            if not raw_url and entry_id:
                raw_url = f"https://www.youtube.com/watch?v={entry_id}"
            duration = raw.get("duration")
            entries.append(
                PlaylistEntry(
                    index=position,
                    id=entry_id or str(position),
                    title=str(raw.get("title") or entry_id or f"Item {position}"),
                    url=raw_url,
                    duration=int(duration) if isinstance(duration, (int, float)) else None,
                )
            )
        return tuple(entries)

    def download(
        self,
        request: DownloadRequest,
        progress_callback: Optional[ProgressCallback] = None,
        should_stop: Optional[ShouldStop] = None,
    ) -> None:
        yt_dlp = self._load_yt_dlp()
        cancel_type = self._yt_dlp_cancel_type(yt_dlp)
        stop_requested = False
        guarded_should_stop: Optional[ShouldStop] = None

        if should_stop is not None:

            def guarded_should_stop() -> bool:
                nonlocal stop_requested
                if should_stop():
                    stop_requested = True
                    return True
                return False

        options = self.build_options(request, progress_callback, guarded_should_stop, cancel_type)

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.download([request.url])
        except Exception as exc:
            if stop_requested:
                raise DownloadCancelled("Download stopped") from exc
            raise

    def build_options(
        self,
        request: DownloadRequest,
        progress_callback: Optional[ProgressCallback] = None,
        should_stop: Optional[ShouldStop] = None,
        cancel_exception: Optional[type] = None,
    ) -> dict:
        request.output_dir.mkdir(parents=True, exist_ok=True)

        if not ffmpeg_available():
            raise RuntimeError("ffmpeg is required. Install ffmpeg and make sure it is on your PATH.")

        options: dict = {
            "outtmpl": str(request.output_dir / build_output_template(request.playlist)),
            "noplaylist": not request.playlist,
            "ignoreerrors": request.playlist,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": self._build_progress_hooks(progress_callback, should_stop, cancel_exception),
            **extraction_options(),
        }

        if request.playlist and request.playlist_items:
            options["playlist_items"] = request.playlist_items

        if request.skip_existing:
            options["overwrites"] = False

        if request.rate_limit_bps > 0:
            options["ratelimit"] = int(request.rate_limit_bps)

        if request.cookies_from_browser:
            options["cookiesfrombrowser"] = (request.cookies_from_browser, None, None, None)

        if request.subtitles and request.mode == DownloadMode.VIDEO:
            options["writesubtitles"] = True
            options["subtitleslangs"] = list(request.subtitle_languages)
            if request.auto_subtitles:
                options["writeautomaticsub"] = True

        postprocessors: List[dict] = []

        if request.mode == DownloadMode.VIDEO:
            preset = VIDEO_QUALITY_BY_KEY.get(request.video_quality_key, VIDEO_QUALITY_BY_KEY["best"])
            options.update(
                {
                    "format": video_format_selector(preset.key),
                    "merge_output_format": request.video_container,
                }
            )
            postprocessors = video_postprocessors(
                video_container=request.video_container,
                embed_thumbnail=request.embed_thumbnail,
                embed_metadata=request.embed_metadata,
                embed_subtitles=request.embed_subtitles and request.subtitles,
            )
        elif request.mode == DownloadMode.AUDIO:
            preset = AUDIO_QUALITY_BY_KEY.get(request.audio_quality_key, AUDIO_QUALITY_BY_KEY["320"])
            options.update({"format": "bestaudio/best"})
            postprocessors = audio_postprocessors(
                audio_format=request.audio_format,
                bitrate_kbps=preset.bitrate_kbps,
                embed_thumbnail=request.embed_thumbnail,
                embed_metadata=request.embed_metadata,
            )
        else:
            raise ValueError(f"Unsupported download mode: {request.mode}")

        postprocessors += sponsorblock_postprocessors(request.sponsorblock_categories)

        if postprocessors:
            options["postprocessors"] = postprocessors

        if any(postprocessor.get("key") == "EmbedThumbnail" for postprocessor in postprocessors):
            options["writethumbnail"] = True

        return options

    def _build_progress_hooks(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        should_stop: Optional[ShouldStop] = None,
        cancel_exception: Optional[type] = None,
    ) -> List[Callable[[dict], None]]:
        if progress_callback is None and should_stop is None:
            return []

        stop_error: type = cancel_exception if cancel_exception is not None else DownloadCancelled

        def hook(data: dict) -> None:
            if should_stop is not None and should_stop():
                raise stop_error("Download stopped")
            if progress_callback is not None:
                progress_callback(DownloadProgress.from_hook_data(data))

        return [hook]

    @staticmethod
    def _yt_dlp_cancel_type(yt_dlp) -> Optional[type]:
        utils = getattr(yt_dlp, "utils", None)
        if utils is None:
            try:
                utils = importlib.import_module("yt_dlp.utils")
            except ModuleNotFoundError:
                return None
        return getattr(utils, "DownloadCancelled", None)

    @staticmethod
    def _load_yt_dlp():
        try:
            return importlib.import_module("yt_dlp")
        except ModuleNotFoundError as exc:
            raise RuntimeError("yt-dlp is not installed. Install dependencies with `pip install -r requirements.txt`.") from exc
