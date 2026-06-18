from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class DownloadMode(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    output_dir: Path
    mode: DownloadMode = DownloadMode.VIDEO
    playlist: bool = False
    video_quality_key: str = "best"
    audio_quality_key: str = "320"


@dataclass(frozen=True)
class DownloadProgress:
    status: str
    title: Optional[str] = None
    filename: Optional[str] = None
    downloaded_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    percentage: Optional[float] = None
    speed_bytes_per_second: Optional[float] = None
    eta_seconds: Optional[int] = None

    @classmethod
    def from_hook_data(cls, data: dict[str, Any]) -> "DownloadProgress":
        info_dict = data.get("info_dict")
        title = None
        if isinstance(info_dict, dict):
            raw_title = info_dict.get("title")
            if raw_title:
                title = str(raw_title)

        downloaded_bytes = data.get("downloaded_bytes")
        total_bytes = data.get("total_bytes") or data.get("total_bytes_estimate")
        percentage = None
        try:
            if downloaded_bytes is not None and total_bytes:
                percentage = float(downloaded_bytes) / float(total_bytes) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            percentage = None

        return cls(
            status=str(data.get("status", "unknown")),
            title=title,
            filename=str(data.get("filename")) if data.get("filename") else None,
            downloaded_bytes=int(downloaded_bytes) if downloaded_bytes is not None else None,
            total_bytes=int(total_bytes) if total_bytes is not None else None,
            percentage=percentage,
            speed_bytes_per_second=float(data.get("speed")) if data.get("speed") is not None else None,
            eta_seconds=int(data.get("eta")) if data.get("eta") is not None else None,
        )

    @property
    def message(self) -> str:
        label = self.title or self.filename or "Item"
        if self.status == "finished":
            return f"Finished: {label}"
        if self.status == "downloading" and self.percentage is not None:
            return f"{label}: {self.percentage:.1f}%"
        return f"{label}: {self.status}"
