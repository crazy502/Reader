"""Isolated real-novel engine used only by the WebView2 experiment.

The module deliberately reuses Notebook's existing ``load_novel`` dispatcher and
``Novel``/``Chapter`` model.  It never imports the formal bookshelf or progress
storage modules, so the experiment cannot write Notebook user data by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import statistics
import sys
import tempfile
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

    def prepare_synthetic(
        self, target_chars: int, *, parse_runs: int = 3
    ) -> dict[str, Any]:
        target = max(20_000, int(target_chars))
        text = generate_synthetic_text(target)
        parse_times: list[float] = []
        novel: Novel | None = None
        with tempfile.TemporaryDirectory(
            prefix="notebook-webview-benchmark-", dir=EXPERIMENT_ROOT
        ) as temporary:
            source = Path(temporary) / f"synthetic-{target}.txt"
            source.write_text(text, encoding="utf-8", newline="")
            for _ in range(max(1, int(parse_runs))):
                started = time.perf_counter()
                novel = load_novel(source)
                parse_times.append((time.perf_counter() - started) * 1000)
        assert novel is not None
        # The temporary source path is metadata only; no later rendering reads it.
        book_id = f"synthetic_{target}_{sha256(text.encode('utf-8')).hexdigest()[:12]}"
        metadata = self.register_novel(
            novel,
            book_id=book_id,
            display_title=f"合成压力测试 {target:,} 字",
            parse_ms=statistics.median(parse_times),
        )
        metadata["parse_runs_ms"] = [round(value, 3) for value in parse_times]
        metadata["parse_median_ms"] = round(statistics.median(parse_times), 3)
        metadata["target_chars"] = target
        return metadata

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


def build_whole_fragments(novel: Novel) -> tuple[TextFragment, ...]:
    """Strategy A: make paragraph/line nodes, all inserted in one DOM operation."""
    heading_starts = {chapter.start_char: chapter.index for chapter in novel.chapters}
    fragments: list[TextFragment] = []
    cursor = 0
    paragraph_start = 0
    for line in novel.text.splitlines(keepends=True):
        if not line:
            continue
        line_end = cursor + len(line)
        cursor = line_end
        paragraph_complete = not line.rstrip("\r\n") or cursor - paragraph_start >= MAX_WHOLE_FRAGMENT_CHARS
        if paragraph_complete:
            _append_whole_range(
                fragments, novel, paragraph_start, cursor, heading_starts
            )
            paragraph_start = cursor
    if paragraph_start < len(novel.text):
        _append_whole_range(
            fragments, novel, paragraph_start, len(novel.text), heading_starts
        )
    if not fragments and novel.text:
        fragments.append(TextFragment(0, len(novel.text), novel.text, 0))
    _assert_exact_fragments(novel.text, fragments)
    return tuple(fragments)


def _append_whole_range(
    fragments: list[TextFragment],
    novel: Novel,
    start: int,
    end: int,
    heading_starts: dict[int, int],
) -> None:
    cursor = start
    while cursor < end:
        fragment_end = min(end, cursor + MAX_WHOLE_FRAGMENT_CHARS)
        chapter_index = chapter_index_for_position(novel.chapters, cursor)
        fragments.append(
            TextFragment(
                cursor,
                fragment_end,
                novel.text[cursor:fragment_end],
                chapter_index,
                "heading" if cursor in heading_starts else "body",
            )
        )
        cursor = fragment_end


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


_SYNTHETIC_PARAGRAPHS = (
    "城里的雨从清晨一直落到黄昏，旧街两旁的梧桐被洗得发亮。林默沿着河岸慢慢走，记下每一扇仍亮着灯的窗，也记下那些来不及说出口的话。",
    "车站的钟比城里的时间慢了七分钟。广播声穿过空旷的候车室，一列夜车在雾里靠站，远行的人提着行李，像从另一段故事中短暂停留。",
    "她把信折好放进书页，纸上有中文、空格、缩进，还有一个微笑 🙂 与音乐符号 𝄞。这些非 BMP 字符专门用于验证 Python code point 和 JavaScript UTF-16 offset 的映射。",
    "　　记忆并不总按时间排列。它更像一间光线昏暗的仓库，某个寻常的声音或气味，都可能碰落一只多年未曾打开的纸箱。",
    "河水从城南绕过，向更远的平原流去。有人说尽头是海，也有人说那里有一座相同的城市，住着一群做过不同选择的人。",
)


def generate_synthetic_text(target_chars: int) -> str:
    """Generate chaptered, paragraph-shaped Chinese text near the requested size."""
    target = max(1_000, int(target_chars))
    chapter_count = max(8, min(600, target // 5_000))
    per_chapter = max(500, target // chapter_count)
    parts: list[str] = []
    length = 0
    for chapter_index in range(chapter_count):
        heading = f"第{chapter_index + 1}章 合成阅读样本 {chapter_index + 1}\n\n"
        parts.append(heading)
        length += len(heading)
        paragraph_index = 0
        chapter_start = length
        while length - chapter_start < per_chapter and length < target:
            paragraph = _SYNTHETIC_PARAGRAPHS[
                (chapter_index + paragraph_index) % len(_SYNTHETIC_PARAGRAPHS)
            ]
            rendered = f"{paragraph}\n\n"
            parts.append(rendered)
            length += len(rendered)
            paragraph_index += 1
        if length >= target:
            break
    text = "".join(parts)
    if len(text) < target:
        repeats = (target - len(text)) // len(_SYNTHETIC_PARAGRAPHS[0]) + 1
        text += (f"{_SYNTHETIC_PARAGRAPHS[0]}\n\n" * repeats)
    return text[:target]


__all__ = [
    "ExperimentLibrary",
    "ExperimentNovelError",
    "TextFragment",
    "build_chunked_fragments",
    "build_whole_fragments",
    "chapter_index_for_position",
    "generate_synthetic_text",
]
