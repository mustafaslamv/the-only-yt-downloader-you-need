import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from youtube_downloader import history


class HistoryTests(unittest.TestCase):
    def test_record_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            entry = history.HistoryEntry(
                url="https://www.youtube.com/watch?v=abc",
                title="Sample",
                kind="video",
                mode="music",
                format="MP3 · 320 kbps",
                status="finished",
                output_dir=temp_dir,
                items=1,
                size_bytes=1024,
            )

            history.record(entry, path=path)
            loaded = history.load(path=path)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].title, "Sample")
        self.assertEqual(loaded[0].status, "finished")
        self.assertEqual(loaded[0].size_bytes, 1024)
        self.assertTrue(loaded[0].timestamp)

    def test_newest_entry_comes_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            for title in ("first", "second"):
                history.record(
                    history.HistoryEntry(
                        url="u",
                        title=title,
                        kind="video",
                        mode="video",
                        format="MP4",
                        status="finished",
                        output_dir=temp_dir,
                    ),
                    path=path,
                )
            loaded = history.load(path=path)

        self.assertEqual([entry.title for entry in loaded], ["second", "first"])

    def test_history_is_capped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            for index in range(history.MAX_ENTRIES + 10):
                history.record(
                    history.HistoryEntry(
                        url="u",
                        title=f"item {index}",
                        kind="video",
                        mode="video",
                        format="MP4",
                        status="finished",
                        output_dir=temp_dir,
                    ),
                    path=path,
                )
            loaded = history.load(path=path)

        self.assertEqual(len(loaded), history.MAX_ENTRIES)

    def test_load_tolerates_missing_or_broken_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = history.load(path=Path(temp_dir) / "nope.json")
            broken_path = Path(temp_dir) / "broken.json"
            broken_path.write_text("{not json", encoding="utf-8")
            broken = history.load(path=broken_path)

        self.assertEqual(missing, [])
        self.assertEqual(broken, [])

    def test_clear_empties_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            history.record(
                history.HistoryEntry(
                    url="u",
                    title="t",
                    kind="video",
                    mode="video",
                    format="MP4",
                    status="finished",
                    output_dir=temp_dir,
                ),
                path=path,
            )
            history.clear(path=path)
            loaded = history.load(path=path)

        self.assertEqual(loaded, [])

    def test_directory_bytes_since_counts_only_new_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_file = root / "old.mp4"
            old_file.write_bytes(b"x" * 100)
            stale = time.time() - 3600
            os.utime(old_file, (stale, stale))

            cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
            new_file = root / "new.mp4"
            new_file.write_bytes(b"x" * 250)
            part_file = root / "new.mp4.part"
            part_file.write_bytes(b"x" * 999)

            size = history.directory_bytes_since(root, cutoff)

        self.assertEqual(size, 250)


if __name__ == "__main__":
    unittest.main()
