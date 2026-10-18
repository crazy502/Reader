from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from reader.webview.storage import (
    NotebookStorage,
    NotebookStorageError,
    resolve_data_dir,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _book(path: Path, content: str = "第一章 开始\n正文") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_import_has_no_data_directory_side_effect(tmp_path: Path) -> None:
    appdata = tmp_path / "roaming"
    appdata.mkdir()
    environment = os.environ.copy()
    environment["APPDATA"] = str(appdata)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("NOTEBOOK_DATA_DIR", None)

    subprocess.run(
        [sys.executable, "-B", "-c", "import reader.webview.storage"],
        check=True,
        cwd=PROJECT_ROOT,
        env=environment,
    )

    assert list(appdata.iterdir()) == []


def test_default_data_dir_and_test_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    appdata = tmp_path / "roaming"
    monkeypatch.delenv("NOTEBOOK_DATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(appdata))
    assert resolve_data_dir() == appdata / "Notebook"

    override = tmp_path / "isolated-test"
    monkeypatch.setenv("NOTEBOOK_DATA_DIR", str(override))
    assert resolve_data_dir() == override.resolve()


def test_add_deduplicates_without_changing_active_book(tmp_path: Path) -> None:
    storage = NotebookStorage(tmp_path / "data")
    first = storage.add_book(_book(tmp_path / "first.txt"))
    storage.state.active_book_id = first["book_id"]
    storage._save_bookshelf()

    second_path = _book(tmp_path / "second.txt")
    second = storage.add_book(second_path)
    duplicate = storage.add_book(second_path)

    assert second["book_id"] == duplicate["book_id"]
    assert storage.state.active_book_id == first["book_id"]
    assert len(storage.snapshot()["books"]) == 2


def test_progress_theme_and_work_note_persist_across_restart(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    storage = NotebookStorage(data_dir)
    record = storage.add_book(_book(tmp_path / "novel.txt"))
    storage.activate_loaded(
        record["book_id"],
        {"text_length": 10_000, "chapter_index": 4, "chapter_title": "第五章"},
    )
    storage.save_position(
        record["book_id"],
        {
            "text_length": 10_000,
            "char_position": 6_250,
            "chapter_index": 4,
            "chapter_title": "第五章",
        },
    )
    storage.save_theme("eye_care")
    storage.save_note("会议记录🙂")

    restored = NotebookStorage(data_dir).snapshot()
    book = restored["books"][0]

    assert restored["reading_theme"] == "eye_care"
    assert restored["work_note"] == "会议记录🙂"
    assert restored["active_book_id"] == record["book_id"]
    assert book["char_position"] == 6_250
    assert book["chapter_title"] == "第五章"
    assert book["progress"] == pytest.approx(0.625)


def test_rename_relocate_and_remove_preserve_disk_files(tmp_path: Path) -> None:
    storage = NotebookStorage(tmp_path / "data")
    original = _book(tmp_path / "original.txt")
    relocated = _book(tmp_path / "moved.txt")
    record = storage.add_book(original)

    assert storage.rename_book(record["book_id"], "新书名")["title"] == "新书名"
    moved = storage.relocate_book(record["book_id"], relocated)
    removed = storage.remove_book(record["book_id"])

    assert moved["book_id"] == record["book_id"]
    assert removed == {"removed": True, "book_id": record["book_id"]}
    assert original.is_file()
    assert relocated.is_file()
    assert storage.snapshot()["books"] == []


def test_relocation_validation_and_atomic_theme_json(tmp_path: Path) -> None:
    storage = NotebookStorage(tmp_path / "data")
    first = storage.add_book(_book(tmp_path / "one.txt"))
    second = storage.add_book(_book(tmp_path / "two.txt"))
    epub = tmp_path / "replacement.epub"
    epub.write_bytes(b"storage-only")

    with pytest.raises(NotebookStorageError):
        storage.relocate_book(first["book_id"], Path(second["file_path"]))
    with pytest.raises(NotebookStorageError):
        storage.relocate_book(first["book_id"], epub)

    assert storage.save_theme("not-a-theme") == "classic"
    assert json.loads(storage.settings_path.read_text(encoding="utf-8")) == {
        "reading_theme": "classic"
    }
    assert list(storage.data_dir.glob("*.tmp")) == []
