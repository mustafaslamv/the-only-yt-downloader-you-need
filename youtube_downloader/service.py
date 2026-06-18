from __future__ import annotations

import importlib
from typing import Callable, List, Optional

from .checks import ffmpeg_available
from .models import DownloadMode, DownloadProgress, DownloadRequest
from .presets import AUDIO_QUALITY_BY_KEY, VIDEO_QUALITY_BY_KEY, audio_postprocessors, build_output_template, video_format_selector

ProgressCallback = Callable[[DownloadProgress], None]


class YouTubeDownloader:
    def download(self, request: DownloadRequest, progress_callback: Optional[ProgressCallback] = None) -> None:
        yt_dlp = self._load_yt_dlp()
        options = self.build_options(request, progress_callback)

        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([request.url])

    def build_options(
        self,
        request: DownloadRequest,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> dict:
        request.output_dir.mkdir(parents=True, exist_ok=True)

        if not ffmpeg_available():
            raise RuntimeError("ffmpeg is required. Install ffmpeg and make sure it is on your PATH.")

        options = {
            "outtmpl": str(request.output_dir / build_output_template(request.playlist)),
            "noplaylist": not request.playlist,
            "ignoreerrors": request.playlist,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": self._build_progress_hooks(progress_callback),
        }

        if request.mode == DownloadMode.VIDEO:
            preset = VIDEO_QUALITY_BY_KEY.get(request.video_quality_key, VIDEO_QUALITY_BY_KEY["best"])
            options.update(
                {
                    "format": video_format_selector(preset.key),
                    "merge_output_format": "mp4",
                }
            )
            return options

        if request.mode == DownloadMode.AUDIO:
            preset = AUDIO_QUALITY_BY_KEY.get(request.audio_quality_key, AUDIO_QUALITY_BY_KEY["320"])
            options.update(
                {
                    "format": "bestaudio/best",
                    "writethumbnail": True,
                    "postprocessors": audio_postprocessors(preset.key),
                }
            )
            return options

        raise ValueError(f"Unsupported download mode: {request.mode}")

    def _build_progress_hooks(self, progress_callback: Optional[ProgressCallback]) -> List[Callable[[dict], None]]:
        if progress_callback is None:
            return []

        def hook(data: dict) -> None:
            progress_callback(DownloadProgress.from_hook_data(data))

        return [hook]

    @staticmethod
    def _load_yt_dlp():
        try:
            return importlib.import_module("yt_dlp")
        except ModuleNotFoundError as exc:
            raise RuntimeError("yt-dlp is not installed. Install dependencies with `pip install -r requirements.txt`.") from exc
