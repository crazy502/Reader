"""Global settings persistence and read-only legacy progress migration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile

from .config import DEFAULT_READING_THEME, normalize_reading_theme


_READING_THEME_KEY = "reading_theme"
_PROGRESS_KEYS = ("file_path", "chapter_index", "char_position")


@dataclass(frozen=True)
class ReadingProgress:
    file_path: str
    chapter_index: int
    char_position: int


def load_progress(path: Path) -> ReadingProgress | None:
    raw = _load_config(path)
    if raw is None:
        return None
    try:
        return ReadingProgress(
            file_path=str(raw["file_path"]),
            chapter_index=max(0, int(raw["chapter_index"])),
            char_position=max(0, int(raw["char_position"])),
        )
    except (ValueError, KeyError, TypeError):
        return None


def load_reading_theme(path: Path) -> str:
    """Load the global reading theme without requiring saved book progress."""
    raw = _load_config(path)
    if raw is None:
        return DEFAULT_READING_THEME
    return normalize_reading_theme(raw.get(_READING_THEME_KEY))


def save_reading_theme(path: Path, reading_theme: str) -> None:
    """Persist the global theme while leaving legacy migration fields untouched."""
    raw = _load_config(path) or {}
    payload = {key: raw[key] for key in _PROGRESS_KEYS if key in raw}
    payload[_READING_THEME_KEY] = normalize_reading_theme(reading_theme)
    _save_config(path, payload)


def _load_config(path: Path) -> dict[str, object] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _save_config(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as temporary:
            temporary_name = Path(temporary.name)
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.flush()
        temporary_name.replace(path)
    except OSError:
        # Reading should never fail merely because persistence is unavailable.
        return
    finally:
        if temporary_name is not None:
            try:
                temporary_name.unlink(missing_ok=True)
            except OSError:
                pass
