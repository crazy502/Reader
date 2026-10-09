from __future__ import annotations

from pathlib import Path

from reader.core import config


def test_development_paths_remain_inside_project() -> None:
    assert config.RESOURCE_ROOT == config.PROJECT_ROOT
    assert config.USER_DATA_DIR == config.PROJECT_ROOT / "data"
    assert config.PROGRESS_FILE == config.USER_DATA_DIR / "reader_config.json"
    assert config.BOOKSHELF_FILE == config.USER_DATA_DIR / "bookshelf.json"
    assert config.WORK_NOTE_FILE == config.USER_DATA_DIR / "work_note.txt"


def test_frozen_user_data_uses_appdata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    user_data_dir = config.resolve_user_data_dir()

    assert user_data_dir == tmp_path / "Reader"
    assert user_data_dir / "bookshelf.json" == tmp_path / "Reader" / "bookshelf.json"
    assert user_data_dir / "work_note.txt" == tmp_path / "Reader" / "work_note.txt"


def test_user_data_directory_is_created(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "Reader"

    assert config.ensure_user_data_dir(target) == target
    assert target.is_dir()


def test_frozen_resource_root_prefers_pyinstaller_bundle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert config.resolve_resource_root() == tmp_path


def test_reading_themes_match_the_fixed_palette() -> None:
    assert config.DEFAULT_READING_THEME == "classic"
    assert {
        name: (theme.background, theme.foreground)
        for name, theme in config.READING_THEMES.items()
    } == {
        "classic": ("#F6F1E7", "#2B2A28"),
        "white": ("#FFFFFF", "#222222"),
        "eye_care": ("#EAF4DF", "#2A2A2A"),
        "parchment": ("#F3E7C9", "#3A3026"),
        "light_gray": ("#F3F3F3", "#222222"),
    }


def test_invalid_reading_theme_falls_back_to_classic() -> None:
    assert config.normalize_reading_theme(None) == "classic"
    assert config.normalize_reading_theme("unknown") == "classic"
    assert config.normalize_reading_theme("white") == "white"
