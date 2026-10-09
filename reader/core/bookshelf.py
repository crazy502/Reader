"""Persistent bookshelf metadata and per-book reading positions."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .progress import ReadingProgress


SCHEMA_VERSION = 1
SUPPORTED_FORMATS = {"txt", "epub"}


class BookshelfError(ValueError):
    """Base class for user-correctable bookshelf operations."""


class DuplicateBookPathError(BookshelfError):
    """Raised when a relocated path already belongs to another record."""


class BookFormatMismatchError(BookshelfError):
    """Raised when relocation changes the book's file format."""


@dataclass(frozen=True)
class BookRecord:
    """One stable bookshelf entry and its latest reading position."""

    book_id: str
    file_path: str
    display_title: str
    file_format: str
    chapter_index: int = 0
    chapter_title: str = ""
    char_position: int = 0
    text_length: int = 0
    last_opened_at: str = ""


@dataclass
class BookshelfState:
    """The complete bookshelf file persisted under USER_DATA_DIR."""

    schema_version: int = SCHEMA_VERSION
    legacy_progress_migrated: bool = False
    active_book_id: str | None = None
    books: dict[str, BookRecord] = field(default_factory=dict)

    def find_by_path(self, path: Path | str) -> BookRecord | None:
        normalized = normalize_book_path(path)
        return next(
            (
                book
                for book in self.books.values()
                if normalize_book_path(book.file_path) == normalized
            ),
            None,
        )

    def add_or_activate(
        self, path: Path | str, opened_at: str | None = None
    ) -> BookRecord:
        """Reuse a path record or add it, then mark it as the active book."""
        absolute_path = absolute_book_path(path)
        existing = self.find_by_path(absolute_path)
        timestamp = opened_at or utc_now_iso()
        if existing is None:
            file_format = book_format_for_path(absolute_path)
            book_id = _available_book_id(self, absolute_path)
            existing = BookRecord(
                book_id=book_id,
                file_path=absolute_path,
                display_title=Path(absolute_path).stem,
                file_format=file_format,
                last_opened_at=timestamp,
            )
        else:
            existing = replace(
                existing,
                file_path=absolute_path,
                last_opened_at=timestamp,
            )
        self.books[existing.book_id] = existing
        self.active_book_id = existing.book_id
        return existing

    def activate(self, book_id: str, opened_at: str | None = None) -> BookRecord:
        book = self.books[book_id]
        updated = replace(book, last_opened_at=opened_at or utc_now_iso())
        self.books[book_id] = updated
        self.active_book_id = book_id
        return updated

    def update_progress(
        self,
        book_id: str,
        *,
        chapter_index: int,
        chapter_title: str,
        char_position: int,
        text_length: int,
    ) -> BookRecord | None:
        book = self.books.get(book_id)
        if book is None:
            return None
        updated = replace(
            book,
            chapter_index=max(0, int(chapter_index)),
            chapter_title=str(chapter_title),
            char_position=max(0, int(char_position)),
            text_length=max(0, int(text_length)),
        )
        self.books[book_id] = updated
        return updated

    def rename(self, book_id: str, display_title: str) -> BookRecord:
        title = display_title.strip()
        if not title:
            raise BookshelfError("display title cannot be empty")
        updated = replace(self.books[book_id], display_title=title)
        self.books[book_id] = updated
        return updated

    def relocate(self, book_id: str, new_path: Path | str) -> BookRecord:
        book = self.books[book_id]
        path = Path(new_path)
        if not path.is_file():
            raise BookshelfError("replacement file does not exist")
        absolute_path = absolute_book_path(path)
        if book_format_for_path(absolute_path) != book.file_format:
            raise BookFormatMismatchError("replacement format does not match")
        owner = self.find_by_path(absolute_path)
        if owner is not None and owner.book_id != book_id:
            raise DuplicateBookPathError("replacement path already belongs to a book")
        updated = replace(book, file_path=absolute_path)
        self.books[book_id] = updated
        return updated

    def remove(self, book_id: str) -> BookRecord | None:
        removed = self.books.pop(book_id, None)
        if self.active_book_id == book_id:
            self.active_book_id = None
        return removed


def absolute_book_path(path: Path | str) -> str:
    """Return a normalized absolute spelling suitable for storage."""
    return str(Path(path).expanduser().resolve(strict=False))


def normalize_book_path(path: Path | str) -> str:
    """Return a case-normalized absolute path for identity comparisons."""
    return os.path.normcase(os.path.normpath(absolute_book_path(path)))


def book_id_for_path(path: Path | str) -> str:
    """Create the immutable initial ID from the normalized absolute path."""
    digest = hashlib.sha256(normalize_book_path(path).encode("utf-8")).hexdigest()
    return f"path_{digest}"


def book_format_for_path(path: Path | str) -> str:
    file_format = Path(path).suffix.lower().lstrip(".")
    if file_format not in SUPPORTED_FORMATS:
        raise BookshelfError("unsupported book format")
    return file_format


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def reading_percentage(book: BookRecord) -> float:
    if book.text_length <= 0:
        return 0.0
    return min(100.0, max(0.0, book.char_position / book.text_length * 100.0))


def books_by_recent_activity(state: BookshelfState) -> list[BookRecord]:
    return sorted(
        state.books.values(),
        key=lambda book: (book.last_opened_at, book.display_title.casefold()),
        reverse=True,
    )


def migrate_legacy_progress(
    state: BookshelfState,
    progress: ReadingProgress | None,
    migrated_at: str | None = None,
) -> bool:
    """Import the old single-book position exactly once.

    The legacy config remains untouched.  The persisted marker prevents a removed
    migrated book from being recreated on a later startup.
    """
    if state.legacy_progress_migrated:
        return False
    state.legacy_progress_migrated = True
    if progress is None or not progress.file_path:
        return True
    try:
        existing = state.find_by_path(progress.file_path)
        if existing is None:
            absolute_path = absolute_book_path(progress.file_path)
            book_id = _available_book_id(state, absolute_path)
            existing = BookRecord(
                book_id=book_id,
                file_path=absolute_path,
                display_title=Path(absolute_path).stem,
                file_format=book_format_for_path(absolute_path),
                chapter_index=max(0, progress.chapter_index),
                char_position=max(0, progress.char_position),
                last_opened_at=migrated_at or utc_now_iso(),
            )
            state.books[book_id] = existing
        state.active_book_id = existing.book_id
    except BookshelfError:
        # Invalid legacy paths are considered migrated but are not added.
        pass
    return True


def load_bookshelf(path: Path) -> BookshelfState:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return BookshelfState()
    if not isinstance(raw, dict):
        return BookshelfState()

    books: dict[str, BookRecord] = {}
    raw_books = raw.get("books")
    if isinstance(raw_books, dict):
        for raw_id, raw_book in raw_books.items():
            record = _record_from_json(raw_id, raw_book)
            if record is not None:
                books[record.book_id] = record
    active_book_id = raw.get("active_book_id")
    if not isinstance(active_book_id, str) or active_book_id not in books:
        active_book_id = None
    return BookshelfState(
        schema_version=SCHEMA_VERSION,
        legacy_progress_migrated=raw.get("legacy_progress_migrated") is True,
        active_book_id=active_book_id,
        books=books,
    )


def _available_book_id(state: BookshelfState, path: Path | str) -> str:
    """Avoid reusing an ID whose original path was later relocated elsewhere."""
    base_id = book_id_for_path(path)
    if base_id not in state.books:
        return base_id
    suffix = 2
    while f"{base_id}_{suffix}" in state.books:
        suffix += 1
    return f"{base_id}_{suffix}"


def save_bookshelf(path: Path, state: BookshelfState) -> bool:
    """Atomically persist the complete bookshelf without raising into the UI."""
    temporary_name: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as temporary:
            temporary_name = Path(temporary.name)
            json.dump(_state_to_json(state), temporary, ensure_ascii=False, indent=2)
            temporary.flush()
        temporary_name.replace(path)
        return True
    except OSError:
        return False
    finally:
        if temporary_name is not None:
            try:
                temporary_name.unlink(missing_ok=True)
            except OSError:
                pass


def _state_to_json(state: BookshelfState) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "legacy_progress_migrated": state.legacy_progress_migrated,
        "active_book_id": state.active_book_id,
        "books": {
            book_id: {
                "file_path": book.file_path,
                "display_title": book.display_title,
                "format": book.file_format,
                "chapter_index": book.chapter_index,
                "chapter_title": book.chapter_title,
                "char_position": book.char_position,
                "text_length": book.text_length,
                "last_opened_at": book.last_opened_at,
            }
            for book_id, book in sorted(state.books.items())
        },
    }


def _record_from_json(raw_id: object, raw_book: object) -> BookRecord | None:
    if not isinstance(raw_id, str) or not raw_id or not isinstance(raw_book, dict):
        return None
    try:
        file_path = str(raw_book["file_path"])
        display_title = str(raw_book["display_title"]).strip()
        file_format = str(raw_book["format"]).lower()
        if not file_path or not display_title or file_format not in SUPPORTED_FORMATS:
            return None
        return BookRecord(
            book_id=raw_id,
            file_path=file_path,
            display_title=display_title,
            file_format=file_format,
            chapter_index=max(0, int(raw_book.get("chapter_index", 0))),
            chapter_title=str(raw_book.get("chapter_title", "")),
            char_position=max(0, int(raw_book.get("char_position", 0))),
            text_length=max(0, int(raw_book.get("text_length", 0))),
            last_opened_at=str(raw_book.get("last_opened_at", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None
