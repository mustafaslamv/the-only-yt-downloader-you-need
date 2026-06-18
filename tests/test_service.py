from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from youtube_downloader.models import DownloadMode, DownloadProgress, DownloadRequest
from youtube_downloader.service import YouTubeDownloader


class YouTubeDownloaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.downloader = YouTubeDownloader()

    def test_build_video_options_for_single_video(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            request = DownloadRequest(
                url="https://www.youtube.com/watch?v=abc123",
                output_dir=Path(temp_dir),
                mode=DownloadMode.VIDEO,
                playlist=False,
                video_quality_key="720",
            )

            options = self.downloader.build_options(request)

            self.assertEqual(options["format"], "bestvideo[height<=720]+bestaudio/best[height<=720]")
            self.assertEqual(options["merge_output_format"], "mp4")
            self.assertTrue(options["noplaylist"])
            self.assertEqual(options["outtmpl"], str(Path(temp_dir) / "%(title)s.%(ext)s"))

    def test_build_audio_options_for_playlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch("youtube_downloader.service.ffmpeg_available", return_value=True):
            request = DownloadRequest(
                url="https://www.youtube.com/playlist?list=PL123",
                output_dir=Path(temp_dir),
                mode=DownloadMode.AUDIO,
                playlist=True,
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
