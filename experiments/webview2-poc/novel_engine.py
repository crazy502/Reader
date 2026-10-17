"""Historical whole-DOM adapter built on the formal WebView2 novel engine."""

from __future__ import annotations

import time
from typing import Any, Literal

from reader.core.novel_parser import Novel
from reader.webview.novel_engine import (
    MAX_CHUNK_CHARS,
    LoadedBook,
    NovelEngineError,
    NovelLibrary,
    TextFragment,
    build_chunked_fragments,
    chapter_as_json,
    chapter_index_for_position,
)
from src.i18n import tr


RenderStrategy = Literal["whole", "chunked"]
MAX_WHOLE_FRAGMENT_CHARS = 16_384
ExperimentNovelError = NovelEngineError
ExperimentBook = LoadedBook


class ExperimentLibrary(NovelLibrary):
    """Add benchmark-only synthetic registration and whole-DOM payloads."""

    def __init__(self) -> None:
        super().__init__()
        self._whole_fragments: dict[str, tuple[TextFragment, ...]] = {}

    def register_novel(
        self,
        novel: Novel,
        *,
        book_id: str,
        display_title: str,
        file_format: str = "TXT",
        parse_ms: float = 0.0,
    ) -> dict[str, Any]:
        book = LoadedBook(
            book_id=book_id,
            novel=novel,
            display_title=display_title,
            file_format=file_format.lower(),
            parse_ms=parse_ms,
        )
        self._books[book_id] = book
        return book.metadata()

    def render_payload(
        self, book_id: str, strategy: RenderStrategy
    ) -> dict[str, Any]:
        if strategy == "chunked":
            return super().render_payload(book_id)
        if strategy != "whole":
            raise ExperimentNovelError(tr("unknown_strategy", strategy=strategy))

        book = self._book(book_id)
        started = time.perf_counter()
        fragments = self._whole_fragments.get(book_id)
        if fragments is None:
            from benchmark_engine import build_whole_fragments

            fragments = build_whole_fragments(book.novel)
            self._whole_fragments[book_id] = fragments
        payload_ms = (time.perf_counter() - started) * 1000
        book.payload_build_ms["whole"] = payload_ms
        payload = book.metadata()
        payload.update(
            {
                "strategy": "whole",
                "fragments": [fragment.as_json() for fragment in fragments],
                "fragment_count": len(fragments),
                "payload_prepare_ms": round(payload_ms, 3),
            }
        )
        return payload


__all__ = [
    "ExperimentBook",
    "ExperimentLibrary",
    "ExperimentNovelError",
    "MAX_CHUNK_CHARS",
    "MAX_WHOLE_FRAGMENT_CHARS",
    "RenderStrategy",
    "TextFragment",
    "build_chunked_fragments",
    "chapter_as_json",
    "chapter_index_for_position",
]
