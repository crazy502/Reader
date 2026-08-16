from __future__ import annotations

import json
from pathlib import Path

import pytest

from reader.core.progress import ReadingProgress, load_progress, save_progress


def test_progress_round_trip_preserves_all_fields(tmp_path: Path) -> None:
    target = tmp_path / "reader_config.json"
    progress = ReadingProgress(
        file_path=str(tmp_path / "novel.txt"),
        chapter_index=14,
        char_position=183742,
    )

    save_progress(target, progress)

    assert load_progress(target) == progress
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "file_path": progress.file_path,
        "chapter_index": 14,
        "char_position": 183742,
    }


def test_missing_progress_file_returns_none(tmp_path: Path) -> None:
    assert load_progress(tmp_path / "missing.json") is None


@pytest.mark.parametrize("content", ["{broken", "[]", '{"file_path": "book.txt"}'])
def test_invalid_progress_returns_none(tmp_path: Path, content: str) -> None:
    target = tmp_path / "reader_config.json"
    target.write_text(content, encoding="utf-8")

    assert load_progress(target) is None


def test_legacy_page_index_is_ignored(tmp_path: Path) -> None:
    target = tmp_path / "reader_config.json"
    target.write_text(
        json.dumps(
            {
                "file_path": "C:/Books/Novel.txt",
                "chapter_index": 7,
                "char_position": 900,
                "page_index": 3,
            }
        ),
        encoding="utf-8",
    )

    assert load_progress(target) == ReadingProgress("C:/Books/Novel.txt", 7, 900)


def test_save_uses_atomic_replace_and_leaves_no_temp_file(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "reader_config.json"
    original_replace = Path.replace
    replacements: list[tuple[Path, Path]] = []

    def tracked_replace(source: Path, destination: Path) -> Path:
        replacements.append((source, destination))
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", tracked_replace)

    save_progress(target, ReadingProgress("C:/Books/Novel.txt", 2, 300))

    assert len(replacements) == 1
    assert replacements[0][1] == target
    assert target.is_file()
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_atomic_replace_preserves_old_file_and_cleans_temp(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "reader_config.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def failed_replace(_source: Path, _destination: Path) -> Path:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", failed_replace)

    save_progress(target, ReadingProgress("C:/Books/Novel.txt", 2, 300))

    assert target.read_text(encoding="utf-8") == '{"old": true}'
    assert not list(tmp_path.glob("*.tmp"))
