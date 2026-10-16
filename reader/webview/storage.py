"""Persistent storage for the WebView2 application."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any


from ..core.bookshelf import (
    BookFormatMismatchError,
    BookRecord,
    BookshelfError,
    BookshelfState,
    DuplicateBookPathError,
    books_by_recent_activity,
    load_bookshelf,
    reading_percentage,
    save_bookshelf,
)
from ..core.work_note import load_work_note, save_work_note
from .i18n import tr


PREVIEW_APP_NAME = "Notebook-Web-Preview"
SUPPORTED_THEMES = {"classic", "white", "eye_care", "parchment", "light_gray"}
DEFAULT_THEME = "classic"


class PreviewStorageError(RuntimeError):
    """User-readable preview persistence or bookshelf error."""


def resolve_preview_data_dir() -> Path:
    """Return the preview-only data directory without consulting formal config."""
    override = os.environ.get("NOTEBOOK_WEB_PREVIEW_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve(strict=False)
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise PreviewStorageError(tr("preview_appdata_required"))
    return Path(appdata) / PREVIEW_APP_NAME


class PreviewStorage:
    """Own the isolated bookshelf, global settings, and editable work note."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = (
            resolve_preview_data_dir()
            if data_dir is None
            else Path(data_dir).expanduser().resolve(strict=False)
        )
        self.bookshelf_path = self.data_dir / "bookshelf.json"
        self.settings_path = self.data_dir / "reader_config.json"
        self.work_note_path = self.data_dir / "work_note.txt"
        self._lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state = load_bookshelf(self.bookshelf_path)
        self._settings = self._load_settings()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": True,
                "active_book_id": self.state.active_book_id,
                "books": [self._book_json(book) for book in books_by_recent_activity(self.state)],
                "reading_theme": self.reading_theme,
                "work_note": load_work_note(self.work_note_path, tr("default_work_note")),
                "data_dir": str(self.data_dir),
            }

    @property
    def reading_theme(self) -> str:
        value = self._settings.get("reading_theme")
        return value if isinstance(value, str) and value in SUPPORTED_THEMES else DEFAULT_THEME

    def add_book(self, path: Path | str) -> dict[str, Any]:
        source = Path(path)
        if not source.is_file():
            raise PreviewStorageError(tr("preview_file_missing"))
        with self._lock:
            existing = self.state.find_by_path(source)
            if existing is not None:
                return self._book_json(existing)
            previous_active = self.state.active_book_id
            try:
                record = self.state.add_or_activate(source)
            except BookshelfError as error:
                raise PreviewStorageError(tr("preview_unsupported_file")) from error
            self.state.active_book_id = previous_active
            self._save_bookshelf()
            return self._book_json(record)

    def record(self, book_id: str) -> BookRecord:
        with self._lock:
            try:
                return self.state.books[str(book_id)]
            except KeyError as error:
                raise PreviewStorageError(tr("preview_book_not_found")) from error

    def activate_loaded(self, book_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Persist a successful load and its clamped position metadata."""
        with self._lock:
            record = self.record(book_id)
            text_length = max(0, int(metadata.get("text_length", 0)))
            position = min(max(0, record.char_position), text_length)
            chapter_index = max(0, int(metadata.get("chapter_index", 0)))
            chapter_title = str(metadata.get("chapter_title", ""))
            self.state.activate(book_id)
            updated = self.state.update_progress(
                book_id,
                chapter_index=chapter_index,
                chapter_title=chapter_title,
                char_position=position,
                text_length=text_length,
            )
            assert updated is not None
            self._save_bookshelf()
            return self._book_json(updated)

    def save_position(self, book_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            updated = self.state.update_progress(
                book_id,
                chapter_index=int(metadata.get("chapter_index", 0)),
                chapter_title=str(metadata.get("chapter_title", "")),
                char_position=int(metadata.get("char_position", 0)),
                text_length=int(metadata.get("text_length", 0)),
            )
            if updated is None:
                return {"removed": True, "book_id": book_id}
            self._save_bookshelf()
            return self._book_json(updated)

    def rename_book(self, book_id: str, title: str) -> dict[str, Any]:
        with self._lock:
            try:
                record = self.state.rename(book_id, title)
            except (KeyError, BookshelfError) as error:
                raise PreviewStorageError(tr("preview_invalid_title")) from error
            self._save_bookshelf()
            return self._book_json(record)

    def relocate_book(self, book_id: str, path: Path | str) -> dict[str, Any]:
        with self._lock:
            try:
                record = self.state.relocate(book_id, path)
            except DuplicateBookPathError as error:
                raise PreviewStorageError(tr("preview_duplicate_relocation")) from error
            except BookFormatMismatchError as error:
                raise PreviewStorageError(tr("preview_format_mismatch")) from error
            except (KeyError, BookshelfError) as error:
                raise PreviewStorageError(tr("preview_relocation_failed")) from error
            self._save_bookshelf()
            return self._book_json(record)

    def remove_book(self, book_id: str) -> dict[str, Any]:
        with self._lock:
            removed = self.state.remove(book_id)
            if removed is None:
                raise PreviewStorageError(tr("preview_book_not_found"))
            self._save_bookshelf()
            return {"removed": True, "book_id": book_id}

    def save_theme(self, theme: str) -> str:
        normalized = theme if theme in SUPPORTED_THEMES else DEFAULT_THEME
        with self._lock:
            self._settings = {"reading_theme": normalized}
            self._atomic_save_json(self.settings_path, self._settings)
        return normalized

    def save_note(self, content: str) -> bool:
        with self._lock:
            if not save_work_note(self.work_note_path, str(content)):
                raise PreviewStorageError(tr("preview_note_save_failed"))
        return True

    def _save_bookshelf(self) -> None:
        if not save_bookshelf(self.bookshelf_path, self.state):
            raise PreviewStorageError(tr("preview_bookshelf_save_failed"))

    def _load_settings(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {"reading_theme": DEFAULT_THEME}
        if not isinstance(payload, dict):
            return {"reading_theme": DEFAULT_THEME}
        return {"reading_theme": payload.get("reading_theme", DEFAULT_THEME)}

    @staticmethod
    def _atomic_save_json(path: Path, payload: dict[str, Any]) -> None:
        temporary_name: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
                suffix=".tmp",
            ) as temporary:
                temporary_name = Path(temporary.name)
                json.dump(payload, temporary, ensure_ascii=False, indent=2)
                temporary.flush()
            temporary_name.replace(path)
        except OSError as error:
            raise PreviewStorageError(tr("preview_settings_save_failed")) from error
        finally:
            if temporary_name is not None:
                try:
                    temporary_name.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _book_json(book: BookRecord) -> dict[str, Any]:
        return {
            "book_id": book.book_id,
            "title": book.display_title,
            "format": book.file_format.upper(),
            "file_path": book.file_path,
            "chapter_index": book.chapter_index,
            "chapter_title": book.chapter_title,
            "char_position": book.char_position,
            "text_length": book.text_length,
            "progress": reading_percentage(book) / 100.0,
            "last_opened_at": book.last_opened_at,
            "missing": not Path(book.file_path).is_file(),
            "external": True,
            "persisted": True,
        }


__all__ = [
    "DEFAULT_THEME",
    "PREVIEW_APP_NAME",
    "PreviewStorage",
    "PreviewStorageError",
    "resolve_preview_data_dir",
]
