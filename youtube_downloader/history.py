from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

_lock = threading.Lock()
MAX_ENTRIES = 50


def default_history_path() -> Path:
    return Path.cwd() / "downloads" / ".history.json"


@dataclass
class HistoryEntry:
    url: str
    title: str
    kind: str
    mode: str
    format: str
    status: str
    output_dir: str
    timestamp: str = ""
    items: int = 1
    size_bytes: Optional[int] = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path: Optional[Path] = None) -> List[HistoryEntry]:
    history_path = path or default_history_path()
    with _lock:
        return [HistoryEntry(**item) for item in _read_raw(history_path)]


def record(entry: HistoryEntry, path: Optional[Path] = None) -> None:
    history_path = path or default_history_path()
    with _lock:
        entries = _read_raw(history_path)
        entries.insert(0, asdict(entry))
        entries = entries[:MAX_ENTRIES]
        _write(history_path, entries)


def clear(path: Optional[Path] = None) -> None:
    history_path = path or default_history_path()
    with _lock:
        _write(history_path, [])


def directory_bytes_since(directory: Path, since: datetime) -> Optional[int]:
    """Total size of files written in `directory` at or after `since`."""
    if not directory.exists():
        return None

    since_ts = since.timestamp()
    total = 0
    try:
        for root, _dirs, files in os.walk(directory):
            for name in files:
                if name.endswith(".part") or name == ".history.json":
                    continue
                file_path = Path(root) / name
                try:
                    if file_path.stat().st_mtime >= since_ts:
                        total += file_path.stat().st_size
                except OSError:
                    continue
    except OSError:
        return None
    return total


def _read_raw(history_path: Path) -> List[dict]:
    try:
        raw = json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []

    known_fields = set(HistoryEntry.__dataclass_fields__)
    entries: List[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entries.append({key: item[key] for key in known_fields if key in item})
    return entries


def _write(history_path: Path, entries: List[dict]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = history_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, history_path)
