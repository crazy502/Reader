from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from preview_storage import PreviewStorage, PreviewStorageError, resolve_preview_data_dir


def _book(path: Path, content: str = "第一章 开始\n正文") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_import_does_not_create_formal_reader_data_dir(tmp_path: Path) -> None:
    appdata = tmp_path / "roaming"
    appdata.mkdir()
    environment = os.environ.copy()
    environment["APPDATA"] = str(appdata)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("NOTEBOOK_WEB_PREVIEW_DATA_DIR", None)
    source = (
        "import sys; "
        "sys.frozen = True; "
        f"sys.path.insert(0, {str(EXPERIMENT_ROOT)!r}); "
        "import preview_storage"
    )

    subprocess.run(
        [sys.executable, "-B", "-c", source],
        check=True,
        cwd=EXPERIMENT_ROOT,
        env=environment,
    )

    assert list(appdata.iterdir()) == []


def test_preview_storage_isolated_snapshot_and_defaults(tmp_path: Path) -> None:
    storage = PreviewStorage(tmp_path / "preview")

    snapshot = storage.snapshot()

    assert snapshot["books"] == []
    assert snapshot["active_book_id"] is None
    assert snapshot["reading_theme"] == "classic"
    assert "今日待处理" in snapshot["work_note"]
    assert Path(snapshot["data_dir"]) == (tmp_path / "preview").resolve()


def test_default_data_dir_uses_appdata_and_honours_test_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    appdata = tmp_path / "roaming"
    monkeypatch.delenv("NOTEBOOK_WEB_PREVIEW_DATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(appdata))
    assert resolve_preview_data_dir() == appdata / "Notebook-Web-Preview"

    override = tmp_path / "isolated-test"
    monkeypatch.setenv("NOTEBOOK_WEB_PREVIEW_DATA_DIR", str(override))
    assert resolve_preview_data_dir() == override.resolve()


def test_add_deduplicates_without_changing_active_book(tmp_path: Path) -> None:
    storage = PreviewStorage(tmp_path / "data")
    first_path = _book(tmp_path / "first.txt")
    second_path = _book(tmp_path / "second.txt")
    first = storage.add_book(first_path)
    storage.state.active_book_id = first["book_id"]
    storage._save_bookshelf()

    second = storage.add_book(second_path)
    duplicate = storage.add_book(second_path)

    assert second["book_id"] == duplicate["book_id"]
    assert storage.state.active_book_id == first["book_id"]
    assert len(storage.snapshot()["books"]) == 2


def test_progress_theme_and_work_note_persist_across_restart(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    storage = PreviewStorage(data_dir)
    record = storage.add_book(_book(tmp_path / "novel.txt"))
    storage.activate_loaded(
        record["book_id"],
        {
            "text_length": 10_000,
            "chapter_index": 4,
            "chapter_title": "第五章",
        },
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

    restored = PreviewStorage(data_dir).snapshot()
    book = restored["books"][0]

    assert restored["reading_theme"] == "eye_care"
    assert restored["work_note"] == "会议记录🙂"
    assert restored["active_book_id"] == record["book_id"]
    assert book["char_position"] == 6_250
    assert book["chapter_title"] == "第五章"
    assert book["progress"] == pytest.approx(0.625)


def test_rename_relocate_and_remove_preserve_disk_files(tmp_path: Path) -> None:
    storage = PreviewStorage(tmp_path / "data")
    original = _book(tmp_path / "original.txt")
    relocated = _book(tmp_path / "moved.txt")
    record = storage.add_book(original)

    renamed = storage.rename_book(record["book_id"], "新书名")
    moved = storage.relocate_book(record["book_id"], relocated)
    removed = storage.remove_book(record["book_id"])

    assert renamed["title"] == "新书名"
    assert moved["book_id"] == record["book_id"]
    assert moved["title"] == "新书名"
    assert removed == {"removed": True, "book_id": record["book_id"]}
    assert original.is_file()
    assert relocated.is_file()
    assert storage.snapshot()["books"] == []


def test_relocation_rejects_duplicate_and_format_change(tmp_path: Path) -> None:
    storage = PreviewStorage(tmp_path / "data")
    first = storage.add_book(_book(tmp_path / "one.txt"))
    second = storage.add_book(_book(tmp_path / "two.txt"))
    epub = tmp_path / "replacement.epub"
    epub.write_bytes(b"not-needed-for-storage-test")

    with pytest.raises(PreviewStorageError):
        storage.relocate_book(first["book_id"], Path(second["file_path"]))
    with pytest.raises(PreviewStorageError):
        storage.relocate_book(first["book_id"], epub)


def test_invalid_theme_falls_back_and_json_is_atomic_shape(tmp_path: Path) -> None:
    storage = PreviewStorage(tmp_path / "data")

    assert storage.save_theme("not-a-theme") == "classic"
    payload = json.loads(storage.settings_path.read_text(encoding="utf-8"))

    assert payload == {"reading_theme": "classic"}
    assert list(storage.data_dir.glob("*.tmp")) == []
