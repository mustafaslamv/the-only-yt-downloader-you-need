from __future__ import annotations

import os
import signal
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from youtube_downloader import history as history_store
from youtube_downloader.checks import ffmpeg_available
from youtube_downloader.models import DownloadMode, DownloadProgress, DownloadRequest, ProbeResult
from youtube_downloader.presets import (
    VIDEO_QUALITY_PRESETS,
    audio_format_from_label,
    audio_format_labels,
    audio_labels,
    audio_preset_from_label,
    playlist_items_string,
    sponsorblock_keys,
    sponsorblock_labels,
    subtitle_language_codes,
    subtitle_language_labels,
    video_container_from_label,
    video_container_labels,
    video_labels,
    video_preset_from_label,
)
from youtube_downloader.service import DownloadCancelled, YouTubeDownloader

JOB_KEY = "download_job"
STOPPING_KEY = "server_stopping"
PROBE_KEY = "probe"
PROBE_URL_KEY = "probe_url"
VISIBLE_LIMIT_KEY = "visible_limit"
HIDDEN_SELECTION_KEY = "sel_hidden"

DEFAULT_VISIBLE_ENTRIES = 100
MAX_VISIBLE_ENTRIES = 500

_shutdown_armed = False


# --------------------------------------------------------------------------- helpers


def human_speed(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    amount = float(value)
    index = 0
    while amount >= 1024 and index < len(units) - 1:
        amount /= 1024
        index += 1
    return f"{amount:.1f} {units[index]}/s"


def fmt_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "--:--"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def fmt_size(size: Optional[int]) -> str:
    if not size:
        return "—"
    amount = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024 or unit == "GB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} GB"


def progress_details(progress: Optional[DownloadProgress]) -> str:
    if progress is None:
        return ""

    parts = []
    if progress.speed_bytes_per_second is not None:
        parts.append(f"Speed: {human_speed(progress.speed_bytes_per_second)}")
    if progress.eta_seconds is not None:
        parts.append(f"ETA: {progress.eta_seconds}s")
    if progress.total_bytes is not None:
        parts.append(f"Size: {fmt_size(progress.total_bytes)}")
    return " | ".join(parts)


def is_playlist_url(url: str) -> bool:
    lowered = url.lower()
    if "/playlist" in lowered:
        return True
    return "list=" in lowered and "v=" not in lowered


def is_single_url(url: str) -> bool:
    lowered = url.lower()
    return "v=" in lowered or "youtu.be/" in lowered or "/shorts/" in lowered or "/live/" in lowered


def clear_selection_keys() -> None:
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.startswith("sel_"):
            st.session_state.pop(key, None)
    st.session_state[VISIBLE_LIMIT_KEY] = DEFAULT_VISIBLE_ENTRIES


def invalidate_probe() -> None:
    st.session_state.pop(PROBE_KEY, None)
    st.session_state.pop(PROBE_URL_KEY, None)


def on_url_change() -> None:
    invalidate_probe()
    url = str(st.session_state.get("url_input", "") or "").strip()
    if is_playlist_url(url):
        st.session_state["scope_label"] = "Playlist"
    elif is_single_url(url):
        st.session_state["scope_label"] = "Single video"


def on_scope_change() -> None:
    invalidate_probe()


def run_probe(url: str, single_video: bool) -> None:
    try:
        probe = YouTubeDownloader().probe(url, single_video=single_video)
    except Exception as error:  # noqa: BLE001 - surfaced to the UI
        invalidate_probe()
        st.error(str(error))
        return

    st.session_state[PROBE_KEY] = probe
    st.session_state[PROBE_URL_KEY] = url
    clear_selection_keys()


# --------------------------------------------------------------------------- wizard pieces


def render_preview(probe: ProbeResult) -> None:
    with st.container(border=True):
        left, right = st.columns([1, 3])
        with left:
            if probe.thumbnail_url:
                st.image(probe.thumbnail_url, width="stretch")
        with right:
            kind = "Playlist" if probe.is_playlist else "Video"
            st.markdown(f"**{probe.title}**")
            bits = []
            if probe.uploader:
                bits.append(probe.uploader)
            bits.append(kind)
            if probe.duration:
                bits.append(fmt_duration(probe.duration))
            if probe.is_playlist:
                bits.append(f"{probe.entry_count} items")
            st.caption(" · ".join(bits))


def render_playlist_picker(probe: ProbeResult) -> List[int]:
    entries = list(probe.entries)
    total = len(entries)
    if total == 0:
        st.warning("This playlist has no readable items.")
        return []

    st.markdown(f"**Choose items to download** ({total} in playlist)")

    limit = int(st.session_state.get(VISIBLE_LIMIT_KEY, DEFAULT_VISIBLE_ENTRIES))
    limit = min(limit, total, MAX_VISIBLE_ENTRIES)

    columns = st.columns([1, 1.4, 1.4, 2.2])
    with columns[0]:
        if st.button("Select shown", width="stretch"):
            for entry in entries[:limit]:
                st.session_state[f"sel_{entry.index}"] = True
    with columns[1]:
        if st.button("Select none", width="stretch"):
            for entry in entries[:limit]:
                st.session_state[f"sel_{entry.index}"] = False
            st.session_state[HIDDEN_SELECTION_KEY] = False
    with columns[2]:
        more = st.button("Show more", width="stretch", disabled=limit >= MAX_VISIBLE_ENTRIES)
        if more:
            st.session_state[VISIBLE_LIMIT_KEY] = limit + DEFAULT_VISIBLE_ENTRIES
            st.rerun()
    with columns[3]:
        st.caption(f"Showing {min(limit, total)} of {total}")

    with st.container(height=320):
        for entry in entries[:limit]:
            label = f"{entry.index:03d} · {entry.title}"
            if entry.duration:
                label += f"  ({fmt_duration(entry.duration)})"
            st.checkbox(label, value=True, key=f"sel_{entry.index}")

    selected = [entry.index for entry in entries[:limit] if st.session_state.get(f"sel_{entry.index}", True)]
    remaining = entries[limit:]
    if remaining:
        st.checkbox(
            f"Also download the remaining {len(remaining)} items",
            value=True,
            key=HIDDEN_SELECTION_KEY,
        )
        if st.session_state.get(HIDDEN_SELECTION_KEY, True):
            selected.extend(entry.index for entry in remaining)

    return selected


def render_options(mode: str) -> Dict[str, Any]:
    """Render the mode dependent option controls and return their values."""
    settings: Dict[str, Any] = {}

    if mode == "Video":
        quality_label = st.selectbox(
            "Video quality",
            video_labels(),
            index=3 if len(VIDEO_QUALITY_PRESETS) > 3 else 0,
            key="video_quality",
        )
        st.caption("The app keeps the best stream at or below this quality cap.")
        container_label = st.selectbox("Video container", video_container_labels(), key="video_container")
        embed_thumbnail = st.checkbox("Embed cover art", value=True, key="video_embed_thumbnail")
        embed_metadata = st.checkbox("Embed title, channel and chapters", value=True, key="video_embed_metadata")

        subtitles = st.checkbox("Download subtitles", value=False, key="subtitles")
        subtitle_languages: List[str] = []
        auto_subtitles = False
        embed_subtitles = False
        if subtitles:
            subtitle_languages = st.multiselect(
                "Subtitle languages",
                subtitle_language_labels(),
                default=["English"],
                key="subtitle_languages",
            )
            auto_subtitles = st.checkbox("Also use auto-generated captions", value=True, key="auto_subtitles")
            embed_subtitles = st.checkbox("Embed subtitles into the video", value=True, key="embed_subtitles")

        settings.update(
            {
                "quality_key": video_preset_from_label(quality_label).key,
                "container": video_container_from_label(container_label).key,
                "embed_thumbnail": embed_thumbnail,
                "embed_metadata": embed_metadata,
                "subtitles": subtitles,
                "subtitle_languages": subtitle_language_codes(subtitle_languages),
                "auto_subtitles": auto_subtitles,
                "embed_subtitles": embed_subtitles,
                "format_label": f"{video_container_from_label(container_label).label} · {quality_label}",
            }
        )
        return settings

    format_label = st.selectbox("Audio format", audio_format_labels(), key="audio_format")
    bitrate_label = st.selectbox("Audio quality", audio_labels(), index=0, key="audio_quality")
    st.caption("MP3 and friends keep the thumbnail embedded automatically.")

    supports_thumbnail = audio_format_from_label(format_label).supports_thumbnail
    embed_thumbnail = st.checkbox(
        "Embed cover art",
        value=True,
        key="audio_embed_thumbnail",
        disabled=not supports_thumbnail,
    )
    if not supports_thumbnail:
        st.caption("WAV files cannot hold embedded cover art, so this option is off.")
    embed_metadata = st.checkbox("Embed title and channel", value=True, key="audio_embed_metadata")

    settings.update(
        {
            "quality_key": "best",
            "audio_key": audio_preset_from_label(bitrate_label).key,
            "audio_format": audio_format_from_label(format_label).key,
            "embed_thumbnail": embed_thumbnail and supports_thumbnail,
            "embed_metadata": embed_metadata,
            "subtitles": False,
            "subtitle_languages": (),
            "auto_subtitles": False,
            "embed_subtitles": False,
            "format_label": f"{audio_format_from_label(format_label).label} · {bitrate_label}",
        }
    )
    return settings


def render_advanced() -> Dict[str, Any]:
    with st.expander("Advanced options"):
        skip_existing = st.checkbox("Skip files that already exist in the folder", value=False, key="skip_existing")
        rate_mb = st.number_input(
            "Max download speed (MB/s, 0 = unlimited)",
            min_value=0,
            max_value=500,
            value=0,
            key="rate_limit_mb",
        )
        cookie_browser = st.selectbox(
            "Browser cookies (needed for age restricted or members only videos)",
            ["None", "chrome", "firefox", "edge", "brave", "opera", "vivaldi"],
            key="cookies_browser",
        )

    return {
        "skip_existing": skip_existing,
        "rate_limit_bps": int(rate_mb) * 1024 * 1024,
        "cookies_from_browser": "" if cookie_browser == "None" else cookie_browser,
    }


def render_history() -> None:
    entries = history_store.load()
    with st.expander(f"Download history ({len(entries)})"):
        if not entries:
            st.caption("Nothing here yet.")
            return
        for entry in entries:
            when = entry.timestamp.replace("T", " ")[:19]
            size = fmt_size(entry.size_bytes)
            status = {"finished": "done", "stopped": "stopped", "error": "failed"}.get(entry.status, entry.status)
            st.markdown(f"**{entry.title}**")
            st.caption(f"{when} UTC · {entry.mode} · {entry.format} · {entry.items} item(s) · {size} · {status}")
            if entry.detail:
                st.caption(entry.detail)


# --------------------------------------------------------------------------- download job


def start_download(request: DownloadRequest, meta: Dict[str, Any]) -> Dict[str, Any]:
    job: Dict[str, Any] = {
        "status": "running",
        "cancel": threading.Event(),
        "progress": None,
        "progress_value": 0,
        "error": None,
        "request": request,
        "meta": meta,
    }

    def on_progress(snapshot: DownloadProgress) -> None:
        job["progress"] = snapshot
        if snapshot.percentage is not None:
            job["progress_value"] = max(0, min(100, int(round(snapshot.percentage))))
        elif snapshot.status == "finished":
            job["progress_value"] = 100

    def run() -> None:
        started = datetime.now(timezone.utc)
        status = "finished"
        detail = ""
        try:
            YouTubeDownloader().download(request, on_progress, should_stop=job["cancel"].is_set)
        except DownloadCancelled:
            status = "stopped"
        except Exception as error:  # noqa: BLE001 - any failure must reach the UI
            status = "error"
            detail = str(error)
        else:
            job["progress_value"] = 100

        job["status"] = status
        job["error"] = detail

        try:
            size = history_store.directory_bytes_since(request.output_dir, started)
            history_store.record(
                history_store.HistoryEntry(
                    url=request.url,
                    title=meta.get("title", request.url),
                    kind=meta.get("kind", "video"),
                    mode=meta.get("mode", "video"),
                    format=meta.get("format", ""),
                    status=status,
                    output_dir=str(request.output_dir),
                    items=int(meta.get("items", 1)),
                    size_bytes=size,
                    detail=detail,
                )
            )
        except Exception:  # noqa: BLE001 - history must never break a download
            pass

    worker = threading.Thread(target=run, name="youtube-download", daemon=True)
    job["thread"] = worker
    worker.start()
    return job


@st.fragment(run_every=0.5)
def render_running_job() -> None:
    job = st.session_state.get(JOB_KEY)
    if not job:
        return

    progress = job.get("progress")
    st.progress(int(job.get("progress_value", 0)))

    if progress is not None:
        st.info(progress.message)
        details = progress_details(progress)
        if details:
            st.caption(details)

    stopping = job["cancel"].is_set()
    if st.button("Stop download", type="primary", width="stretch", disabled=stopping):
        job["cancel"].set()

    if job["cancel"].is_set():
        st.caption("Stopping the download, this can take a moment...")

    if job["status"] != "running":
        st.rerun(scope="app")


def render_job_result(job: Dict[str, Any]) -> None:
    status = job["status"]
    request: DownloadRequest = job["request"]
    progress = job.get("progress")
    meta = job.get("meta", {})

    if status == "finished":
        st.progress(100)
        st.success("Download complete")
        st.success(f"Files saved in: {request.output_dir}")
    elif status == "stopped":
        st.progress(int(job.get("progress_value", 0)))
        st.warning("Download stopped.")
        if progress is not None:
            st.caption(progress.message)
    else:
        st.error("Download failed")
        st.error(job.get("error") or "Unknown error")

    if meta.get("title"):
        st.caption(f"{meta.get('title')} · {meta.get('format', '')}")

    if st.button("Dismiss", width="stretch"):
        st.session_state.pop(JOB_KEY, None)
        st.rerun()


# --------------------------------------------------------------------------- shutdown


def arm_server_shutdown() -> None:
    """Terminate the Streamlit process behind this app (idempotent)."""
    global _shutdown_armed
    if _shutdown_armed:
        return
    _shutdown_armed = True

    job = st.session_state.get(JOB_KEY)
    if job is not None and job.get("status") == "running":
        job["cancel"].set()

    pid = os.getpid()

    def terminate() -> None:
        time.sleep(2.0)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        time.sleep(5.0)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    threading.Thread(target=terminate, name="server-shutdown", daemon=True).start()


# --------------------------------------------------------------------------- main


def render_wizard() -> None:
    mode = st.segmented_control(
        "1. What do you want?",
        ["Video", "Music"],
        key="mode_label",
        default="Video",
    )
    scope = st.segmented_control(
        "2. What to download?",
        ["Single video", "Playlist"],
        key="scope_label",
        default="Single video",
        on_change=on_scope_change,
    )
    mode = mode or "Video"
    scope = scope or "Single video"

    with st.form("fetch_form"):
        url = st.text_input(
            "YouTube URL",
            key="url_input",
            placeholder="https://www.youtube.com/watch?v=... or .../playlist?list=...",
        )
        fetched = st.form_submit_button("Fetch details", type="primary")

    url = str(url or "").strip()

    if fetched:
        if not url:
            st.error("Please paste a YouTube URL.")
        else:
            with st.spinner("Reading the URL..."):
                run_probe(url, single_video=(scope == "Single video"))

    probe: Optional[ProbeResult] = st.session_state.get(PROBE_KEY)
    probe_url = st.session_state.get(PROBE_URL_KEY)
    ready = bool(probe) and bool(url) and probe_url == url

    if url and not ready:
        st.info("Click **Fetch details** to load a preview before downloading.")

    if probe and url and probe_url != url:
        st.warning("The URL changed — Fetch details again to update the preview.")
        ready = False

    selected: List[int] = []
    if ready and probe is not None:
        render_preview(probe)

        if scope == "Playlist" and not probe.is_playlist:
            st.info("No playlist was found at this URL, so it will download as a single video.")
        if scope == "Single video" and probe.is_playlist:
            st.info("Switch to **Playlist** in step 2 to choose which items to download.")

        if probe.is_playlist:
            selected = render_playlist_picker(probe)
            if not selected:
                st.warning("Select at least one item to download.")

    st.divider()
    settings = render_options(mode)
    st.multiselect(
        "Skip sections with SponsorBlock (optional)",
        sponsorblock_labels(),
        key="sponsorblock",
        help="Segments are cut out of the downloaded file. Leave empty to keep everything.",
    )
    advanced = render_advanced()

    can_start = ready and probe is not None and ffmpeg_available() and (
        not probe.is_playlist or bool(selected)
    )
    if not ffmpeg_available():
        st.error("ffmpeg is required — install it and restart the app.")

    with st.form("start_form"):
        output_dir = st.text_input("Save to folder", key="output_dir", value=str(Path.cwd() / "downloads"))
        submitted = st.form_submit_button("Start download", type="primary", disabled=not can_start)

    if submitted:
        folder = str(output_dir or "").strip()
        if not (ready and probe is not None):
            st.error("Fetch the URL first, then start the download.")
        elif not folder:
            st.error("Please choose a folder to save into.")
        else:
            download_mode = DownloadMode.VIDEO if mode == "Video" else DownloadMode.AUDIO
            request = DownloadRequest(
                url=url,
                output_dir=Path(folder).expanduser(),
                mode=download_mode,
                playlist=probe.is_playlist,
                video_quality_key=settings.get("quality_key", "best"),
                audio_quality_key=settings.get("audio_key", "320"),
                audio_format=settings.get("audio_format", "mp3"),
                video_container=settings.get("container", "mp4"),
                embed_thumbnail=bool(settings.get("embed_thumbnail", True)),
                embed_metadata=bool(settings.get("embed_metadata", True)),
                subtitles=bool(settings.get("subtitles", False)),
                subtitle_languages=tuple(settings.get("subtitle_languages", ())),
                auto_subtitles=bool(settings.get("auto_subtitles", False)),
                embed_subtitles=bool(settings.get("embed_subtitles", False)),
                sponsorblock_categories=sponsorblock_keys(st.session_state.get("sponsorblock", [])),
                playlist_items=playlist_items_string(selected) if probe.is_playlist else "",
                skip_existing=bool(advanced.get("skip_existing", False)),
                rate_limit_bps=int(advanced.get("rate_limit_bps", 0)),
                cookies_from_browser=str(advanced.get("cookies_from_browser", "")),
            )
            meta = {
                "title": probe.title,
                "kind": "playlist" if probe.is_playlist else "video",
                "mode": "music" if mode == "Music" else "video",
                "format": settings.get("format_label", ""),
                "items": len(selected) if probe.is_playlist else 1,
            }
            st.session_state[JOB_KEY] = start_download(request, meta)
            st.rerun()

    render_history()


def main() -> None:
    st.set_page_config(page_title="YouTube Downloader", page_icon="⬇️", layout="centered")

    st.title("YouTube Downloader")
    st.caption("Download a video, a playlist, or just the music. Pick the format, fetch, then start.")

    if not ffmpeg_available():
        st.warning("ffmpeg was not found on your PATH. Video merging, thumbnail embedding and audio export need it.")

    st.info("Use this for content you are allowed to download.")

    st.sidebar.caption(f"Server PID: {os.getpid()}")
    stopping_server = bool(st.session_state.get(STOPPING_KEY))
    if st.sidebar.button("Stop server", width="stretch", disabled=stopping_server):
        st.session_state[STOPPING_KEY] = True
        stopping_server = True

    if stopping_server:
        arm_server_shutdown()
        st.sidebar.warning("Stopping the server...")
        st.warning("Stopping the server. This page will disconnect in a moment.")

    job = st.session_state.get(JOB_KEY)
    if job is not None:
        if job["status"] == "running":
            render_running_job()
        else:
            render_job_result(job)
        return

    render_wizard()


if __name__ == "__main__":
    main()
