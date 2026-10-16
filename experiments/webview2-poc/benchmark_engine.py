"""Synthetic books and the historical whole-DOM benchmark strategy."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import statistics
import tempfile
import time
from typing import Any

from novel_engine import (
    MAX_WHOLE_FRAGMENT_CHARS,
    ExperimentLibrary,
    TextFragment,
    chapter_index_for_position,
)
from reader.core.novel_parser import Novel
from reader.loaders import load_novel


EXPERIMENT_ROOT = Path(__file__).resolve().parent


def prepare_synthetic(
    library: ExperimentLibrary, target_chars: int, *, parse_runs: int = 3
) -> dict[str, Any]:
    """Build a temporary synthetic book for the retained benchmark suite."""
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
    book_id = f"synthetic_{target}_{sha256(text.encode('utf-8')).hexdigest()[:12]}"
    metadata = library.register_novel(
        novel,
        book_id=book_id,
        display_title=f"合成压力测试 {target:,} 字",
        parse_ms=statistics.median(parse_times),
    )
    metadata["parse_runs_ms"] = [round(value, 3) for value in parse_times]
    metadata["parse_median_ms"] = round(statistics.median(parse_times), 3)
    metadata["target_chars"] = target
    return metadata


def build_whole_fragments(novel: Novel) -> tuple[TextFragment, ...]:
    """Historical strategy A: insert paragraph/line nodes in one DOM operation."""
    heading_starts = {chapter.start_char: chapter.index for chapter in novel.chapters}
    fragments: list[TextFragment] = []
    cursor = 0
    paragraph_start = 0
    for line in novel.text.splitlines(keepends=True):
        if not line:
            continue
        line_end = cursor + len(line)
        cursor = line_end
        paragraph_complete = (
            not line.rstrip("\r\n")
            or cursor - paragraph_start >= MAX_WHOLE_FRAGMENT_CHARS
        )
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
    """Generate chaptered Chinese text near the requested benchmark size."""
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
        text += f"{_SYNTHETIC_PARAGRAPHS[0]}\n\n" * repeats
    return text[:target]


__all__ = [
    "build_whole_fragments",
    "generate_synthetic_text",
    "prepare_synthetic",
]
