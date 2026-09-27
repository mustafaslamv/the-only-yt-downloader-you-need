from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from youtube_downloader.models import DownloadMode, DownloadProgress, DownloadRequest, ProbeKind
from youtube_downloader.service import DownloadCancelled, YouTubeDownloader


class _FakeCancel(Exception):
    """Stands in for yt_dlp.utils.DownloadCancelled."""


class _FakeYoutubeDL:
    INFO = None
    LAST_OPTIONS = None

    def __init__(self, options: dict) -> None:
        self.options = options
        _FakeYoutubeDL.LAST_OPTIONS = options

    def __enter__(self) -> "_FakeYoutubeDL":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False

    def download(self, urls) -> None:
        for hook in self.options.get("progress_hooks", []):
            hook({"status": "downloading", "filename": "video.mp4", "downloaded_bytes": 10, "total_bytes": 20})

    def extract_info(self, url, download=False, process=True):
        return self.INFO


def _fake_yt_dlp(info=None):
    _FakeYoutubeDL.INFO = info
    return types.SimpleNamespace(
        YoutubeDL=_FakeYoutubeDL,
        utils=types.SimpleNamespace(DownloadCancelled=_FakeCancel),
    )


def _request(temp_dir: str, **overrides) -> DownloadRequest:
    values = dict(
        url="https://www.youtube.com/watch?v=abc123",
        output_dir=Path(temp_dir),
        mode=DownloadMode.VIDEO,
        playlist=False,
        video_quality_key="720",
    )
    values.update(overrides)
    return DownloadRequest(**values)


class YouTubeDownloaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.downloader = YouTubeDownloader()
        _FakeYoutubeDL.INFO = None
        _FakeYoutubeDL.LAST_OPTIONS = None

    # ---------------------------------------------------------------- options

    def test_build_video_options_for_single_video(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            request = _request(temp_dir)

            options = self.downloader.build_options(request)

            self.assertEqual(options["format"], "bestvideo[height<=720]+bestaudio/best[height<=720]")
            self.assertEqual(options["merge_output_format"], "mp4")
            self.assertTrue(options["noplaylist"])
            self.assertEqual(options["outtmpl"], str(Path(temp_dir) / "%(title)s.%(ext)s"))

    def test_build_audio_options_for_playlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            request = _request(
                temp_dir,
                url="https://www.youtube.com/playlist?list=PL123",
                mode=DownloadMode.AUDIO,
                playlist=True,
                video_quality_key="best",
                audio_quality_key="320",
            )

            options = self.downloader.build_options(request)

            self.assertEqual(options["format"], "bestaudio/best")
            self.assertFalse(options["noplaylist"])
            self.assertTrue(options["writethumbnail"])
            self.assertEqual(
                options["outtmpl"],
                str(Path(temp_dir) / "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"),
            )
            postprocessor_keys = [postprocessor["key"] for postprocessor in options["postprocessors"]]
            self.assertEqual(postprocessor_keys[0], "FFmpegExtractAudio")
            self.assertIn("EmbedThumbnail", postprocessor_keys)
            self.assertIn("FFmpegMetadata", postprocessor_keys)

    def test_video_options_include_container_and_embeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            request = _request(temp_dir, video_container="mkv")

            options = self.downloader.build_options(request)

            self.assertEqual(options["merge_output_format"], "mkv")
            self.assertTrue(options["writethumbnail"])
            postprocessor_keys = [postprocessor["key"] for postprocessor in options["postprocessors"]]
            self.assertIn("EmbedThumbnail", postprocessor_keys)
            self.assertIn("FFmpegMetadata", postprocessor_keys)

    def test_wav_format_skips_thumbnail_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            request = _request(
                temp_dir,
                mode=DownloadMode.AUDIO,
                playlist=False,
                audio_quality_key="320",
                audio_format="wav",
            )

            options = self.downloader.build_options(request)

            postprocessor_keys = [postprocessor["key"] for postprocessor in options["postprocessors"]]
            self.assertIn("FFmpegExtractAudio", postprocessor_keys)
            self.assertNotIn("EmbedThumbnail", postprocessor_keys)
            self.assertNotIn("writethumbnail", options)

    def test_playlist_items_are_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            request = _request(
                temp_dir,
                url="https://www.youtube.com/playlist?list=PL123",
                playlist=True,
                playlist_items="1,3,7",
            )

            options = self.downloader.build_options(request)

            self.assertEqual(options["playlist_items"], "1,3,7")

    def test_subtitle_options_apply_to_video_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            video_options = self.downloader.build_options(
                _request(temp_dir, subtitles=True, subtitle_languages=("en", "ar"), auto_subtitles=True, embed_subtitles=True)
            )
            audio_options = self.downloader.build_options(
                _request(temp_dir, mode=DownloadMode.AUDIO, audio_quality_key="320", subtitles=True, subtitle_languages=("en",))
            )

            self.assertTrue(video_options["writesubtitles"])
            self.assertTrue(video_options["writeautomaticsub"])
            self.assertEqual(video_options["subtitleslangs"], ["en", "ar"])
            self.assertIn(
                "FFmpegEmbedSubtitle",
                [postprocessor["key"] for postprocessor in video_options["postprocessors"]],
            )
            self.assertNotIn("writesubtitles", audio_options)

    def test_sponsorblock_adds_both_postprocessors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            request = _request(temp_dir, sponsorblock_categories=("sponsor", "intro"))

            options = self.downloader.build_options(request)

            keys = [postprocessor["key"] for postprocessor in options["postprocessors"]]
            self.assertIn("SponsorBlock", keys)
            self.assertIn("ModifyChapters", keys)
            modify = next(pp for pp in options["postprocessors"] if pp["key"] == "ModifyChapters")
            self.assertEqual(set(modify["remove_sponsor_segments"]), {"sponsor", "intro"})
            sponsor = next(pp for pp in options["postprocessors"] if pp["key"] == "SponsorBlock")
            self.assertEqual(set(sponsor["categories"]), {"sponsor", "intro"})

    def test_advanced_options_are_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            request = _request(
                temp_dir,
                skip_existing=True,
                rate_limit_bps=1024 * 1024,
                cookies_from_browser="firefox",
            )

            options = self.downloader.build_options(request)

            self.assertFalse(options["overwrites"])
            self.assertEqual(options["ratelimit"], 1024 * 1024)
            self.assertEqual(options["cookiesfrombrowser"], ("firefox", None, None, None))

    def test_options_enable_js_runtime_and_remote_components(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            options = self.downloader.build_options(_request(temp_dir))

            self.assertEqual(options["js_runtimes"], {"deno": {}, "node": {}})
            self.assertEqual(options["remote_components"], ["ejs:github"])

    def test_each_call_gets_fresh_extraction_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            first = self.downloader.build_options(_request(temp_dir))
            first["js_runtimes"].pop("node")
            second = self.downloader.build_options(_request(temp_dir))

            self.assertIn("node", second["js_runtimes"])

    def test_missing_ffmpeg_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=False):
            with self.assertRaises(RuntimeError):
                self.downloader.build_options(_request(temp_dir))

    # ---------------------------------------------------------------- cancel / progress

    def test_progress_hook_stops_download_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            options = self.downloader.build_options(_request(temp_dir), should_stop=lambda: True)

            hooks = options["progress_hooks"]
            self.assertEqual(len(hooks), 1)
            with self.assertRaises(DownloadCancelled):
                hooks[0]({"status": "downloading", "filename": "video.mp4"})

    def test_progress_hook_reports_progress_while_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            seen = []
            options = self.downloader.build_options(
                _request(temp_dir),
                progress_callback=seen.append,
                should_stop=lambda: False,
            )
            options["progress_hooks"][0](
                {"status": "downloading", "filename": "video.mp4", "downloaded_bytes": 50, "total_bytes": 100}
            )

            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0].percentage, 50.0)

    def test_download_converts_stop_into_download_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "youtube_downloader.service.ffmpeg_available", return_value=True
        ), patch.object(YouTubeDownloader, "_load_yt_dlp", return_value=_fake_yt_dlp()):
            with self.assertRaises(DownloadCancelled):
                self.downloader.download(_request(temp_dir), should_stop=lambda: True)

    def test_download_reports_progress_without_stopping(self) -> None:
        seen = []
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "youtube_downloader.service.ffmpeg_available", return_value=True
        ), patch.object(YouTubeDownloader, "_load_yt_dlp", return_value=_fake_yt_dlp()):
            self.downloader.download(
                _request(temp_dir),
                progress_callback=seen.append,
                should_stop=lambda: False,
            )

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].percentage, 50.0)

    # ---------------------------------------------------------------- probe

    def test_probe_reads_single_video(self) -> None:
        info = {
            "_type": None,
            "id": "abc123",
            "title": "Sample Video",
            "uploader": "Sample Channel",
            "duration": 125,
            "thumbnails": [{"url": "https://img.example/thumb.jpg"}],
        }
        with patch.object(YouTubeDownloader, "_load_yt_dlp", return_value=_fake_yt_dlp(info)):
            probe = self.downloader.probe("https://www.youtube.com/watch?v=abc123", single_video=True)

        self.assertIs(probe.kind, ProbeKind.VIDEO)
        self.assertEqual(probe.title, "Sample Video")
        self.assertEqual(probe.uploader, "Sample Channel")
        self.assertEqual(probe.duration, 125)
        self.assertEqual(probe.thumbnail_url, "https://img.example/thumb.jpg")
        self.assertEqual(probe.entry_count, 1)
        self.assertEqual(_FakeYoutubeDL.LAST_OPTIONS["noplaylist"], True)

    def test_probe_reads_playlist_entries(self) -> None:
        info = {
            "_type": "playlist",
            "title": "My List",
            "channel": "List Channel",
            "entries": [
                {"id": "one", "title": "First", "duration": 60, "url": "https://www.youtube.com/watch?v=one"},
                None,
                {"id": "three", "title": "Third", "duration": 90, "url": "three"},
            ],
        }
        with patch.object(YouTubeDownloader, "_load_yt_dlp", return_value=_fake_yt_dlp(info)):
            probe = self.downloader.probe("https://www.youtube.com/playlist?list=PL1")

        self.assertIs(probe.kind, ProbeKind.PLAYLIST)
        self.assertTrue(probe.is_playlist)
        self.assertEqual(probe.title, "My List")
        self.assertEqual(probe.uploader, "List Channel")
        self.assertEqual(probe.entry_count, 3)
        self.assertEqual([entry.index for entry in probe.entries], [1, 3])
        self.assertEqual(probe.entries[1].url, "https://www.youtube.com/watch?v=three")
        self.assertEqual(_FakeYoutubeDL.LAST_OPTIONS["noplaylist"], False)
        self.assertEqual(_FakeYoutubeDL.LAST_OPTIONS["extract_flat"], "in_playlist")

    def test_probe_reports_empty_results(self) -> None:
        with patch.object(YouTubeDownloader, "_load_yt_dlp", return_value=_fake_yt_dlp(None)):
            with self.assertRaises(RuntimeError):
                self.downloader.probe("https://www.youtube.com/watch?v=missing")

    # ---------------------------------------------------------------- misc

    def test_progress_snapshot_from_hook_data(self) -> None:
        snapshot = DownloadProgress.from_hook_data(
            {
                "status": "downloading",
                "filename": "video.mp4",
                "downloaded_bytes": 50,
                "total_bytes": 100,
                "speed": 25,
                "eta": 2,
                "info_dict": {"title": "Sample Video"},
            }
        )

        self.assertEqual(snapshot.status, "downloading")
        self.assertEqual(snapshot.title, "Sample Video")
        self.assertEqual(snapshot.percentage, 50.0)
        self.assertEqual(snapshot.message, "Sample Video: 50.0%")


if __name__ == "__main__":
    unittest.main()
