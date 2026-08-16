"""Crash-tolerant UTF-8 persistence for the editable work note."""

from __future__ import annotations

from pathlib import Path
import tempfile


def load_work_note(path: Path, default_text: str) -> str:
    """Load a work note, returning the supplied template when unavailable."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return default_text


def save_work_note(path: Path, content: str) -> bool:
    """Atomically save a work note without allowing persistence errors to escape."""
    temporary_name: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as temporary:
            temporary_name = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
        temporary_name.replace(path)
        return True
    except (OSError, UnicodeError):
        return False
    finally:
        if temporary_name is not None:
            try:
                temporary_name.unlink(missing_ok=True)
            except OSError:
                pass
