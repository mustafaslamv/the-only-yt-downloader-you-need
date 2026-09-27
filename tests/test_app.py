import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from youtube_downloader.models import PlaylistEntry, ProbeKind, ProbeResult

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
VIDEO_URL = "https://www.youtube.com/watch?v=abc123"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL123"


def video_probe(url: str = VIDEO_URL) -> ProbeResult:
    return ProbeResult(
        kind=ProbeKind.VIDEO,
        url=url,
        title="Sample Video",
        uploader="Sample Channel",
        duration=125,
        thumbnail_url="https://img.example/thumb.jpg",
        entry_count=1,
    )


def playlist_probe(url: str = PLAYLIST_URL) -> ProbeResult:
    entries = tuple(
        PlaylistEntry(index=index, id=f"id{index}", title=f"Item {index}", url=f"https://youtu.be/id{index}", duration=60)
        for index in (1, 2, 3)
    )
    return ProbeResult(
        kind=ProbeKind.PLAYLIST,
        url=url,
        title="Sample Playlist",
        uploader="Sample Channel",
        thumbnail_url=None,
        entry_count=3,
        entries=entries,
    )


class AppWizardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._ffmpeg = patch("youtube_downloader.checks.ffmpeg_available", return_value=True)
        self._ffmpeg.start()
        self.addCleanup(self._ffmpeg.stop)
        self.at = AppTest.from_file(str(APP_PATH), default_timeout=15)

    @staticmethod
    def _button(at: AppTest, label: str):
        matches = [button for button in at.button if button.label == label]
        if not matches:
            raise AssertionError(f"button {label!r} not found among {[b.label for b in at.button]}")
        return matches[0]

    @staticmethod
    def _set_url(at: AppTest, url: str) -> None:
        at.text_input(key="url_input").set_value(url)
        at.run()

    def _prepare(self, url: str, probe: ProbeResult) -> None:
        """Set the URL and inject an already fetched probe for it."""
        self.at.run()
        self._set_url(self.at, url)
        self.at.session_state["probe"] = probe
        self.at.session_state["probe_url"] = url
        self.at.run()

    def test_wizard_loads_with_two_steps(self) -> None:
        self.at.run()

        self.assertEqual(self.at.exception, [])
        self.assertEqual(len(self.at.segmented_control), 2)
        self.assertEqual(self.at.segmented_control[0].value, "Video")
        self.assertEqual(self.at.segmented_control[1].value, "Single video")
        self._button(self.at, "Fetch details")
        self.assertTrue(self._button(self.at, "Start download").disabled)

    def test_start_disabled_until_fetched(self) -> None:
        self.at.run()
        self._set_url(self.at, VIDEO_URL)

        self.assertTrue(self._button(self.at, "Start download").disabled)
        info_values = [info.value for info in self.at.info]
        self.assertTrue(any("Fetch details" in value for value in info_values))

    def test_video_preview_enables_start(self) -> None:
        self._prepare(VIDEO_URL, video_probe())

        self.assertEqual(self.at.exception, [])
        markdown = " ".join(markdown.value for markdown in self.at.markdown)
        self.assertIn("Sample Video", markdown)
        self.assertFalse(self._button(self.at, "Start download").disabled)

    def test_playlist_shows_selection_and_needs_an_item(self) -> None:
        self._prepare(PLAYLIST_URL, playlist_probe())

        labels = [checkbox.label for checkbox in self.at.checkbox]
        self.assertTrue(any(label.startswith("001 · Item 1") for label in labels))
        self.assertTrue(any(label.startswith("002 · Item 2") for label in labels))
        self.assertFalse(self._button(self.at, "Start download").disabled)

        self._button(self.at, "Select none").click().run()

        self.assertTrue(self._button(self.at, "Start download").disabled)
        self.assertIn("Select at least one item to download.", [warning.value for warning in self.at.warning])

    def test_changing_url_invalidates_the_preview(self) -> None:
        self._prepare(VIDEO_URL, video_probe())

        self._set_url(self.at, "https://www.youtube.com/watch?v=other")

        self.assertTrue(self._button(self.at, "Start download").disabled)
        warnings = [warning.value for warning in self.at.warning]
        self.assertTrue(any("Fetch details again" in warning for warning in warnings))

    def test_music_mode_shows_audio_controls(self) -> None:
        self.at.run()
        self.at.segmented_control[0].set_value("Music").run()

        labels = [selectbox.label for selectbox in self.at.selectbox]
        self.assertIn("Audio format", labels)
        self.assertIn("Audio quality", labels)
        self.assertNotIn("Video quality", labels)

    def test_video_mode_shows_video_controls(self) -> None:
        self.at.run()

        labels = [selectbox.label for selectbox in self.at.selectbox]
        self.assertIn("Video quality", labels)
        self.assertIn("Video container", labels)

    def test_advanced_options_render(self) -> None:
        self.at.run()

        labels = [checkbox.label for checkbox in self.at.checkbox]
        self.assertIn("Skip files that already exist in the folder", labels)
        number_labels = [number_input.label for number_input in self.at.number_input]
        self.assertTrue(any("Max download speed" in label for label in number_labels))


if __name__ == "__main__":
    unittest.main()
