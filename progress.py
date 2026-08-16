"""Crash-tolerant JSON persistence for the last reading location."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class ReadingProgress:
    file_path: str
    chapter_index: int
    char_position: int


def load_progress(path: Path) -> ReadingProgress | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ReadingProgress(
            file_path=str(raw["file_path"]),
            chapter_index=max(0, int(raw["chapter_index"])),
            char_position=max(0, int(raw["char_position"])),
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def save_progress(path: Path, progress: ReadingProgress) -> None:
    """Replace the JSON atomically so an interrupted save leaves the old file valid."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as temporary:
            json.dump(asdict(progress), temporary, ensure_ascii=False, indent=2)
            temporary.flush()
            temporary_name = Path(temporary.name)
        temporary_name.replace(path)
    except OSError:
        # Reading should never fail merely because persistence is unavailable.
        return
