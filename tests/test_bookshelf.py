from __future__ import annotations

import json
from pathlib import Path

import pytest

from reader.core.bookshelf import (
    BookFormatMismatchError,
    BookshelfState,
    DuplicateBookPathError,
    books_by_recent_activity,
    load_bookshelf,
    migrate_legacy_progress,
    reading_percentage,
    save_bookshelf,
)
from reader.core.progress import (
    ReadingProgress,
    load_reading_theme,
    save_reading_theme,
)


def _book_file(directory: Path, name: str, content: str = "body") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


def test_two_books_keep_independent_progress_across_restart(tmp_path: Path) -> None:
    shelf_file = tmp_path / "bookshelf.json"
    book_a_path = _book_file(tmp_path, "A.txt")
    book_b_path = _book_file(tmp_path, "B.txt")
    state = BookshelfState(legacy_progress_migrated=True)

    book_a = state.add_or_activate(book_a_path, "2026-09-13T08:00:00Z")
    state.update_progress(
        book_a.book_id,
        chapter_index=2,
        chapter_title="第三章",
        char_position=320,
        text_length=1000,
    )
    book_b = state.add_or_activate(book_b_path, "2026-09-13T09:00:00Z")
    state.update_progress(
        book_b.book_id,
        chapter_index=7,
        chapter_title="第八章",
        char_position=890,
        text_length=2000,
    )
    state.activate(book_a.book_id, "2026-09-13T10:00:00Z")

    assert save_bookshelf(shelf_file, state)
    restored = load_bookshelf(shelf_file)

    assert restored.active_book_id == book_a.book_id
    assert restored.books[book_a.book_id].char_position == 320
    assert restored.books[book_a.book_id].chapter_index == 2
    assert restored.books[book_b.book_id].char_position == 890
    assert restored.books[book_b.book_id].chapter_index == 7


def test_txt_and_epub_can_share_one_bookshelf(tmp_path: Path) -> None:
    txt = _book_file(tmp_path, "Novel.txt")
    epub = _book_file(tmp_path, "Novel.epub")
    state = BookshelfState(legacy_progress_migrated=True)

    txt_book = state.add_or_activate(txt)
    epub_book = state.add_or_activate(epub)

    assert txt_book.file_format == "txt"
    assert epub_book.file_format == "epub"
    assert len(state.books) == 2


def test_same_filename_in_different_directories_has_distinct_ids(tmp_path: Path) -> None:
    first = _book_file(tmp_path / "one", "Game.txt")
    second = _book_file(tmp_path / "two", "Game.txt")
    state = BookshelfState(legacy_progress_migrated=True)

    first_book = state.add_or_activate(first)
    second_book = state.add_or_activate(second)

    assert first_book.book_id != second_book.book_id
    assert first_book.display_title == second_book.display_title == "Game"
    assert len(state.books) == 2


def test_reopening_same_path_does_not_duplicate_or_reset_metadata(tmp_path: Path) -> None:
    path = _book_file(tmp_path, "Game.txt")
    state = BookshelfState(legacy_progress_migrated=True)
    first = state.add_or_activate(path, "2026-09-13T08:00:00Z")
    state.rename(first.book_id, "神明游戏")
    state.update_progress(
        first.book_id,
        chapter_index=8,
        chapter_title="第九章",
        char_position=900,
        text_length=5000,
    )

    reopened = state.add_or_activate(path, "2026-09-13T09:00:00Z")

    assert reopened.book_id == first.book_id
    assert reopened.display_title == "神明游戏"
    assert reopened.char_position == 900
    assert reopened.last_opened_at == "2026-09-13T09:00:00Z"
    assert len(state.books) == 1


def test_legacy_progress_is_migrated_only_once(tmp_path: Path) -> None:
    legacy = ReadingProgress(str(tmp_path / "Old.txt"), 12, 3456)
    state = BookshelfState()

    assert migrate_legacy_progress(state, legacy, "2026-09-13T08:00:00Z")
    migrated_id = state.active_book_id
    assert migrated_id is not None
    assert state.books[migrated_id].chapter_index == 12
    assert state.books[migrated_id].char_position == 3456

    assert not migrate_legacy_progress(
        state,
        ReadingProgress(str(tmp_path / "Other.txt"), 1, 2),
        "2026-09-13T09:00:00Z",
    )
    assert len(state.books) == 1
    assert migrated_id in state.books


def test_removed_legacy_book_is_not_recreated_after_restart(tmp_path: Path) -> None:
    shelf_file = tmp_path / "bookshelf.json"
    legacy = ReadingProgress(str(tmp_path / "Old.txt"), 4, 500)
    state = BookshelfState()
    migrate_legacy_progress(state, legacy)
    migrated_id = state.active_book_id
    assert migrated_id is not None
    state.remove(migrated_id)
    save_bookshelf(shelf_file, state)

    restarted = load_bookshelf(shelf_file)

    assert restarted.legacy_progress_migrated
    assert not migrate_legacy_progress(restarted, legacy)
    assert restarted.books == {}
    assert restarted.active_book_id is None


def test_missing_file_record_is_retained(tmp_path: Path) -> None:
    shelf_file = tmp_path / "bookshelf.json"
    missing = tmp_path / "Moved.epub"
    state = BookshelfState(legacy_progress_migrated=True)
    book = state.add_or_activate(missing)
    state.update_progress(
        book.book_id,
        chapter_index=3,
        chapter_title="Chapter 4",
        char_position=450,
        text_length=900,
    )

    save_bookshelf(shelf_file, state)
    restored = load_bookshelf(shelf_file)

    assert book.book_id in restored.books
    assert restored.books[book.book_id].file_path == str(missing.resolve())
    assert restored.books[book.book_id].char_position == 450


def test_relocation_preserves_id_title_and_progress(tmp_path: Path) -> None:
    old_path = _book_file(tmp_path / "old", "Game.txt")
    new_path = _book_file(tmp_path / "new", "RenamedOnDisk.txt")
    state = BookshelfState(legacy_progress_migrated=True)
    book = state.add_or_activate(old_path)
    state.rename(book.book_id, "神明游戏")
    state.update_progress(
        book.book_id,
        chapter_index=20,
        chapter_title="第二十一章",
        char_position=119666,
        text_length=500000,
    )

    relocated = state.relocate(book.book_id, new_path)

    assert relocated.book_id == book.book_id
    assert relocated.display_title == "神明游戏"
    assert relocated.file_path == str(new_path.resolve())
    assert relocated.chapter_index == 20
    assert relocated.char_position == 119666


def test_reopening_a_relocated_original_path_gets_a_new_id(tmp_path: Path) -> None:
    original_path = _book_file(tmp_path / "old", "Game.txt")
    relocated_path = _book_file(tmp_path / "new", "Game.txt")
    state = BookshelfState(legacy_progress_migrated=True)
    original = state.add_or_activate(original_path)
    state.relocate(original.book_id, relocated_path)

    replacement = state.add_or_activate(original_path)

    assert replacement.book_id != original.book_id
    assert state.books[original.book_id].file_path == str(relocated_path.resolve())
    assert len(state.books) == 2


def test_relocation_rejects_path_owned_by_another_book(tmp_path: Path) -> None:
    first_path = _book_file(tmp_path, "First.txt")
    second_path = _book_file(tmp_path, "Second.txt")
    state = BookshelfState(legacy_progress_migrated=True)
    first = state.add_or_activate(first_path)
    state.add_or_activate(second_path)

    with pytest.raises(DuplicateBookPathError):
        state.relocate(first.book_id, second_path)

    assert state.books[first.book_id].file_path == str(first_path.resolve())


def test_relocation_requires_same_file_format(tmp_path: Path) -> None:
    txt = _book_file(tmp_path, "Novel.txt")
    epub = _book_file(tmp_path, "Novel.epub")
    state = BookshelfState(legacy_progress_migrated=True)
    book = state.add_or_activate(txt)

    with pytest.raises(BookFormatMismatchError):
        state.relocate(book.book_id, epub)


def test_recent_sort_and_runtime_percentage(tmp_path: Path) -> None:
    state = BookshelfState(legacy_progress_migrated=True)
    old = state.add_or_activate(
        _book_file(tmp_path, "Old.txt"), "2026-09-12T08:00:00Z"
    )
    recent = state.add_or_activate(
        _book_file(tmp_path, "Recent.txt"), "2026-09-13T08:00:00Z"
    )
    state.update_progress(
        old.book_id,
        chapter_index=0,
        chapter_title="第一章",
        char_position=25,
        text_length=100,
    )

    assert [book.book_id for book in books_by_recent_activity(state)] == [
        recent.book_id,
        old.book_id,
    ]
    assert reading_percentage(state.books[old.book_id]) == 25.0
    assert state.books[old.book_id].last_opened_at == "2026-09-12T08:00:00Z"


def test_removing_active_book_stops_later_progress_updates(tmp_path: Path) -> None:
    state = BookshelfState(legacy_progress_migrated=True)
    book = state.add_or_activate(_book_file(tmp_path, "Novel.txt"))

    state.remove(book.book_id)

    assert state.active_book_id is None
    assert (
        state.update_progress(
            book.book_id,
            chapter_index=3,
            chapter_title="第四章",
            char_position=400,
            text_length=1000,
        )
        is None
    )
    assert state.books == {}


def test_persisted_schema_keeps_progress_only_in_bookshelf(tmp_path: Path) -> None:
    target = tmp_path / "bookshelf.json"
    state = BookshelfState(legacy_progress_migrated=True)
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
    saved_book = payload["books"][book.book_id]

    assert payload["active_book_id"] == book.book_id
    assert saved_book["chapter_index"] == 6
    assert saved_book["chapter_title"] == "Chapter Seven"
    assert saved_book["char_position"] == 700
    assert saved_book["text_length"] == 1400
    assert "reading_theme" not in payload


def test_bookshelf_saves_do_not_change_global_reading_theme(tmp_path: Path) -> None:
    config_file = tmp_path / "reader_config.json"
    shelf_file = tmp_path / "bookshelf.json"
    save_reading_theme(config_file, "eye_care")
    state = BookshelfState(legacy_progress_migrated=True)
    state.add_or_activate(_book_file(tmp_path, "Novel.txt"))

    save_bookshelf(shelf_file, state)

    assert load_reading_theme(config_file) == "eye_care"
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        "reading_theme": "eye_care"
    }


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

    assert save_bookshelf(target, BookshelfState(legacy_progress_migrated=True))
    assert replacements == [(replacements[0][0], target)]
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_bookshelf_replace_preserves_old_file_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "bookshelf.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def failed_replace(_source: Path, _destination: Path) -> Path:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", failed_replace)

    assert not save_bookshelf(target, BookshelfState(legacy_progress_migrated=True))
    assert target.read_text(encoding="utf-8") == '{"old": true}'
    assert not list(tmp_path.glob("*.tmp"))
