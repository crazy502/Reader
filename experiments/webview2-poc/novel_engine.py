"""Isolated real-novel engine used only by the WebView2 experiment.

The module deliberately reuses Notebook's existing ``load_novel`` dispatcher and
``Novel``/``Chapter`` model.  It never imports the formal bookshelf or progress
storage modules, so the experiment cannot write Notebook user data by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import sys
import time
from typing import Any, Literal


EXPERIMENT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENT_ROOT.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reader.core.novel_parser import Chapter, Novel, NovelLoadError  # noqa: E402
from reader.loaders import load_novel  # noqa: E402
from src.i18n import tr  # noqa: E402


RenderStrategy = Literal["whole", "chunked"]
MAX_WHOLE_FRAGMENT_CHARS = 16_384
MAX_CHUNK_CHARS = 65_536


class ExperimentNovelError(ValueError):
    """A user-readable failure confined to the WebView2 experiment."""


@dataclass(frozen=True)
class TextFragment:
    start: int
    end: int
    text: str
    chapter_index: int
    kind: str = "body"

    def as_json(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "chapter_index": self.chapter_index,
            "kind": self.kind,
        }


@dataclass
class ExperimentBook:
    book_id: str
    novel: Novel
    display_title: str
    file_format: str
    parse_ms: float
    char_position: int = 0
    whole_fragments: tuple[TextFragment, ...] | None = None
    chunked_fragments: tuple[TextFragment, ...] | None = None
    payload_build_ms: dict[str, float] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        position = min(max(0, self.char_position), len(self.novel.text))
        chapter_index = chapter_index_for_position(self.novel.chapters, position)
        return {
            "book_id": self.book_id,
            "title": self.display_title,
            "format": self.file_format.upper(),
            "path": str(self.novel.path),
            "text_length": len(self.novel.text),
            "char_position": position,
            "chapter_index": chapter_index,
            "chapter_title": self.novel.chapters[chapter_index].title,
            "chapter_count": len(self.novel.chapters),
            "chapters": [chapter_as_json(chapter) for chapter in self.novel.chapters],
            "parse_ms": round(self.parse_ms, 3),
            "external": True,
        }


class ExperimentLibrary:
    """In-memory A/B book state; no formal config files are read or written."""

    def __init__(self) -> None:
        self._books: dict[str, ExperimentBook] = {}
        self._path_ids: dict[str, str] = {}

    def open_path(self, path: str | Path) -> dict[str, Any]:
        source = Path(path).expanduser().resolve(strict=False)
        if source.suffix.lower() not in {".txt", ".epub"}:
            raise ExperimentNovelError(tr("only_txt_epub"))
        if not source.is_file():
            raise ExperimentNovelError(tr("file_not_found", path=source))
        normalized = str(source).casefold()
        existing_id = self._path_ids.get(normalized)
        if existing_id is not None:
            return self._books[existing_id].metadata()

        started = time.perf_counter()
        try:
            novel = load_novel(source)
        except (OSError, UnicodeError, NovelLoadError) as error:
            raise ExperimentNovelError(tr("load_failed", name=source.name)) from error
        parse_ms = (time.perf_counter() - started) * 1000
        if not novel.text or not novel.chapters:
            raise ExperimentNovelError(tr("empty_novel"))

        book_id = "path_" + sha256(normalized.encode("utf-8")).hexdigest()
        book = ExperimentBook(
            book_id=book_id,
            novel=novel,
            display_title=source.stem,
            file_format=source.suffix.lower().lstrip("."),
            parse_ms=parse_ms,
        )
        self._books[book_id] = book
        self._path_ids[normalized] = book_id
        return book.metadata()

    def register_novel(
        self,
        novel: Novel,
        *,
        book_id: str,
        display_title: str,
        file_format: str = "TXT",
        parse_ms: float = 0.0,
    ) -> dict[str, Any]:
        book = ExperimentBook(
            book_id=book_id,
            novel=novel,
            display_title=display_title,
            file_format=file_format.lower(),
            parse_ms=parse_ms,
        )
        self._books[book_id] = book
        return book.metadata()

    def metadata(self, book_id: str) -> dict[str, Any]:
        return self._book(book_id).metadata()

    def save_position(self, book_id: str, char_position: int) -> dict[str, Any]:
        book = self._book(book_id)
        book.char_position = min(max(0, int(char_position)), len(book.novel.text))
        return book.metadata()

    def render_payload(
        self, book_id: str, strategy: RenderStrategy
    ) -> dict[str, Any]:
        book = self._book(book_id)
        started = time.perf_counter()
        if strategy == "whole":
            if book.whole_fragments is None:
                from benchmark_engine import build_whole_fragments

                book.whole_fragments = build_whole_fragments(book.novel)
            fragments = book.whole_fragments
        elif strategy == "chunked":
            if book.chunked_fragments is None:
                book.chunked_fragments = build_chunked_fragments(book.novel)
            fragments = book.chunked_fragments
        else:
            raise ExperimentNovelError(tr("unknown_strategy", strategy=strategy))

        payload_ms = (time.perf_counter() - started) * 1000
        book.payload_build_ms[strategy] = payload_ms
        payload = book.metadata()
        payload.update(
            {
                "strategy": strategy,
                "fragments": [fragment.as_json() for fragment in fragments],
                "fragment_count": len(fragments),
                "payload_prepare_ms": round(payload_ms, 3),
            }
        )
        return payload

    def _book(self, book_id: str) -> ExperimentBook:
        try:
            return self._books[str(book_id)]
        except KeyError as error:
            raise ExperimentNovelError(tr("book_not_loaded")) from error


def chapter_as_json(chapter: Chapter) -> dict[str, Any]:
    return {
        "index": chapter.index,
        "title": chapter.title,
        "start_char": chapter.start_char,
        "end_char": chapter.end_char,
    }


def chapter_index_for_position(chapters: tuple[Chapter, ...], position: int) -> int:
    if not chapters:
        return 0
    low = 0
    high = len(chapters)
    while low < high:
        middle = (low + high) // 2
        if chapters[middle].start_char <= position:
            low = middle + 1
        else:
            high = middle
    return max(0, low - 1)


def build_chunked_fragments(novel: Novel) -> tuple[TextFragment, ...]:
    """Strategy B: compact chapter/text blocks suitable for incremental insertion."""
    fragments: list[TextFragment] = []
    cursor = 0
    for chapter in novel.chapters:
        if cursor < chapter.start_char:
            _append_sized_chunks(
                fragments, novel.text, cursor, chapter.start_char, max(0, chapter.index - 1)
            )
        heading_end = min(chapter.end_char, chapter.start_char + len(chapter.title))
        if chapter.start_char < heading_end:
            fragments.append(
                TextFragment(
                    chapter.start_char,
                    heading_end,
                    novel.text[chapter.start_char:heading_end],
                    chapter.index,
                    "heading",
                )
            )
        _append_sized_chunks(
            fragments,
            novel.text,
            heading_end,
            chapter.end_char,
            chapter.index,
        )
        cursor = chapter.end_char
    if cursor < len(novel.text):
        _append_sized_chunks(
            fragments,
            novel.text,
            cursor,
            len(novel.text),
            max(0, len(novel.chapters) - 1),
        )
    if not fragments and novel.text:
        _append_sized_chunks(fragments, novel.text, 0, len(novel.text), 0)
    _assert_exact_fragments(novel.text, fragments)
    return tuple(fragments)


def _append_sized_chunks(
    fragments: list[TextFragment],
    text: str,
    start: int,
    end: int,
    chapter_index: int,
) -> None:
    cursor = start
    while cursor < end:
        proposed = min(end, cursor + MAX_CHUNK_CHARS)
        if proposed < end:
            newline = text.rfind("\n", cursor + MAX_CHUNK_CHARS // 2, proposed)
            if newline > cursor:
                proposed = newline + 1
        fragments.append(
            TextFragment(cursor, proposed, text[cursor:proposed], chapter_index)
        )
        cursor = proposed


def _assert_exact_fragments(text: str, fragments: list[TextFragment]) -> None:
    if not fragments:
        if text:
            raise AssertionError("non-empty text produced no fragments")
        return
    if fragments[0].start != 0 or fragments[-1].end != len(text):
        raise AssertionError("fragment range does not cover Novel.text")
    for left, right in zip(fragments, fragments[1:]):
        if left.end != right.start:
            raise AssertionError("fragment ranges are not contiguous")
    if "".join(fragment.text for fragment in fragments) != text:
        raise AssertionError("fragment text changed Novel.text")


__all__ = [
    "ExperimentLibrary",
    "ExperimentNovelError",
    "TextFragment",
    "build_chunked_fragments",
    "chapter_index_for_position",
]
