from __future__ import annotations

import json
from pathlib import Path

import pytest

from reader.core.bookshelf import BookshelfState, load_bookshelf, save_bookshelf


def _book_file(directory: Path, name: str, content: str = "body") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


def test_two_books_keep_independent_progress_across_restart(tmp_path: Path) -> None:
    target = tmp_path / "bookshelf.json"
    state = BookshelfState()
    first = state.add_or_activate(_book_file(tmp_path, "A.txt"))
    second = state.add_or_activate(_book_file(tmp_path, "B.epub"))
    state.update_progress(
        first.book_id,
        chapter_index=2,
        chapter_title="第三章",
        char_position=320,
        text_length=1000,
    )
    state.update_progress(
        second.book_id,
        chapter_index=7,
        chapter_title="第八章",
        char_position=890,
        text_length=2000,
    )
    state.activate(first.book_id)

    assert save_bookshelf(target, state)
    restored = load_bookshelf(target)

    assert restored.active_book_id == first.book_id
    assert restored.books[first.book_id].char_position == 320
    assert restored.books[second.book_id].char_position == 890


def test_reopening_same_path_does_not_duplicate_or_reset_progress(
    tmp_path: Path,
) -> None:
    source = _book_file(tmp_path, "Game.txt")
    state = BookshelfState()
    first = state.add_or_activate(source)
    state.update_progress(
        first.book_id,
        chapter_index=8,
        chapter_title="第九章",
        char_position=900,
        text_length=5000,
    )

    reopened = state.add_or_activate(source)

    assert reopened.book_id == first.book_id
    assert reopened.char_position == 900
    assert len(state.books) == 1


def test_removing_book_preserves_source_and_rejects_late_progress(
    tmp_path: Path,
) -> None:
    source = _book_file(tmp_path, "Novel.txt")
    state = BookshelfState()
    book = state.add_or_activate(source)

    state.remove(book.book_id)

    assert source.is_file()
    assert state.active_book_id is None
    assert state.update_progress(
        book.book_id,
        chapter_index=3,
        chapter_title="第四章",
        char_position=400,
        text_length=1000,
    ) is None


def test_persisted_schema_keeps_book_progress(tmp_path: Path) -> None:
    target = tmp_path / "bookshelf.json"
    state = BookshelfState()
    book = state.add_or_activate(_book_file(tmp_path, "Novel.epub"))
    state.update_progress(
        book.book_id,
        chapter_index=6,
        chapter_title="Chapter Seven",
        char_position=700,
        text_length=1400,
    )

    assert save_bookshelf(target, state)
    payload = json.loads(target.read_text(encoding="utf-8"))
    saved = payload["books"][book.book_id]
    assert saved["chapter_index"] == 6
    assert saved["char_position"] == 700
    assert saved["text_length"] == 1400


def test_bookshelf_save_is_atomic_and_cleans_temp_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "bookshelf.json"
    original_replace = Path.replace
    replacements: list[tuple[Path, Path]] = []

    def tracked_replace(source: Path, destination: Path) -> Path:
        replacements.append((source, destination))
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", tracked_replace)

    assert save_bookshelf(target, BookshelfState())
    assert replacements == [(replacements[0][0], target)]
    assert not list(tmp_path.glob("*.tmp"))
