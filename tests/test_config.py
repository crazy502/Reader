from __future__ import annotations

from pathlib import Path

from reader.core import config


def test_development_paths_remain_inside_project() -> None:
    assert config.RESOURCE_ROOT == config.PROJECT_ROOT
    assert config.USER_DATA_DIR == config.PROJECT_ROOT / "data"
    assert config.PROGRESS_FILE == config.USER_DATA_DIR / "reader_config.json"
    assert config.WORK_NOTE_FILE == config.USER_DATA_DIR / "work_note.txt"


def test_frozen_user_data_uses_appdata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    user_data_dir = config.resolve_user_data_dir()

    assert user_data_dir == tmp_path / "Reader"
    assert user_data_dir / "work_note.txt" == tmp_path / "Reader" / "work_note.txt"


def test_user_data_directory_is_created(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "Reader"

    assert config.ensure_user_data_dir(target) == target
    assert target.is_dir()


def test_frozen_resource_root_prefers_pyinstaller_bundle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert config.resolve_resource_root() == tmp_path
