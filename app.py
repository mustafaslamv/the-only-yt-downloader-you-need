from __future__ import annotations

from pathlib import Path

import streamlit as st

from youtube_downloader.checks import ffmpeg_available
from youtube_downloader.models import DownloadMode, DownloadRequest
from youtube_downloader.presets import (
    VIDEO_QUALITY_PRESETS,
    audio_labels,
    audio_preset_from_label,
    video_labels,
    video_preset_from_label,
)
from youtube_downloader.service import YouTubeDownloader


def human_speed(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    amount = float(value)
    index = 0
    while amount >= 1024 and index < len(units) - 1:
        amount /= 1024
        index += 1
    return f"{amount:.1f} {units[index]}/s"


def main() -> None:
    st.set_page_config(page_title="YouTube Downloader", layout="centered")

    st.title("YouTube Downloader")
    st.caption("Download a single video or a full playlist. Save music as MP3 with the thumbnail embedded.")

    if not ffmpeg_available():
        st.warning("ffmpeg was not found on your PATH. Video merging and audio thumbnail embedding need ffmpeg.")

    st.info("Use this for content you are allowed to download.")

    downloader = YouTubeDownloader()
    default_output = str(Path.cwd() / "downloads")

    with st.form("download_form"):
        url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
        output_dir = st.text_input("Save to folder", value=default_output)
        mode_label = st.radio("Download type", ["Video", "Music"], horizontal=True)
        download_playlist = st.checkbox("Download entire playlist", value=False)

        if mode_label == "Video":
            quality_label = st.selectbox("Video quality", video_labels(), index=3 if len(VIDEO_QUALITY_PRESETS) > 3 else 0)
            st.caption("The app keeps the best stream at or below this quality cap.")
        else:
            quality_label = st.selectbox("Audio quality", audio_labels(), index=0)
            st.caption("The app exports MP3 audio and embeds the thumbnail automatically.")

        submitted = st.form_submit_button("Start download")

    if not submitted:
        return

    if not url.strip():
        st.error("Please paste a YouTube URL.")
        return

    download_mode = DownloadMode.VIDEO if mode_label == "Video" else DownloadMode.AUDIO
    request = DownloadRequest(
        url=url.strip(),
        output_dir=Path(output_dir).expanduser(),
        mode=download_mode,
        playlist=download_playlist,
        video_quality_key=video_preset_from_label(quality_label).key if download_mode == DownloadMode.VIDEO else "best",
        audio_quality_key=audio_preset_from_label(quality_label).key if download_mode == DownloadMode.AUDIO else "320",
    )

    progress_bar = st.progress(0)
    status_box = st.empty()
    details_box = st.empty()

    def on_progress(snapshot) -> None:
        if snapshot.percentage is not None:
            progress_bar.progress(max(0, min(100, int(round(snapshot.percentage)))))
        if snapshot.status == "finished":
            progress_bar.progress(100)

        status_box.info(snapshot.message)

        extra_details = []
        if snapshot.speed_bytes_per_second is not None:
            extra_details.append(f"Speed: {human_speed(snapshot.speed_bytes_per_second)}")
        if snapshot.eta_seconds is not None:
            extra_details.append(f"ETA: {snapshot.eta_seconds}s")
        if snapshot.total_bytes is not None:
            extra_details.append(f"Size: {snapshot.total_bytes / (1024 * 1024):.1f} MB")

        if extra_details:
            details_box.write(" | ".join(extra_details))
        else:
            details_box.empty()

    try:
        with st.spinner("Downloading..."):
            downloader.download(request, on_progress)
        progress_bar.progress(100)
        status_box.success("Download complete")
        st.success(f"Files saved in: {request.output_dir}")
    except Exception as error:
        status_box.error("Download failed")
        st.error(str(error))


if __name__ == "__main__":
    main()
