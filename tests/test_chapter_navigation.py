from __future__ import annotations

from reader.core.novel_parser import Chapter
from reader.ui.chapter_navigation import (
    chapter_index_for_position,
    matching_chapter_indices,
)


def _chapters(*titles: str) -> tuple[Chapter, ...]:
    return tuple(
        Chapter(index, title, "", index * 100, (index + 1) * 100, index + 1)
        for index, title in enumerate(titles)
    )


def test_chapter_position_lookup_uses_boundaries() -> None:
    starts = (10, 100, 250)

    assert chapter_index_for_position(starts, 0) == 0
    assert chapter_index_for_position(starts, 10) == 0
    assert chapter_index_for_position(starts, 99) == 0
    assert chapter_index_for_position(starts, 100) == 1
    assert chapter_index_for_position(starts, 999) == 2
    assert chapter_index_for_position((), 50) == 0


def test_numeric_search_matches_chapter_title() -> None:
    chapters = _chapters("第 12 章 开始", "第 327 章 儿童节", "第 328 章 继续")

    assert matching_chapter_indices(chapters, "327") == [1]


def test_keyword_search_preserves_original_order() -> None:
    chapters = _chapters("第一章 儿童节", "第二章 日常", "第三章 儿童节后")

    assert matching_chapter_indices(chapters, "儿童节") == [0, 2]


def test_full_width_and_half_width_search_are_equivalent() -> None:
    chapters = _chapters("第３２７章 测试", "第328章 继续")

    assert matching_chapter_indices(chapters, "327") == [0]
    assert matching_chapter_indices(chapters, "３２７") == [0]


def test_search_is_case_insensitive() -> None:
    chapters = _chapters("Chapter 1: Beginning", "Chapter 2: ENDING")

    assert matching_chapter_indices(chapters, "ending") == [1]
    assert matching_chapter_indices(chapters, "CHAPTER") == [0, 1]


def test_empty_search_restores_all_chapters() -> None:
    chapters = _chapters("第一章", "第二章", "第三章")

    assert matching_chapter_indices(chapters, "") == [0, 1, 2]
    assert matching_chapter_indices(chapters, "  ") == [0, 1, 2]
