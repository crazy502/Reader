"""Application configuration and filesystem locations."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


APP_NAME = "Reader"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_resource_root() -> Path:
    """Locate bundled resources without coupling user data to the executable."""
    if getattr(sys, "frozen", False):
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            return Path(bundle_root)
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def resolve_user_data_dir() -> Path:
    """Use project data while developing and APPDATA in a frozen build."""
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA is required for a frozen Windows build")
        return Path(appdata) / APP_NAME
    return PROJECT_ROOT / "data"


def ensure_user_data_dir(directory: Path | None = None) -> Path:
    """Create and return the selected user data directory."""
    selected = resolve_user_data_dir() if directory is None else directory
    selected.mkdir(parents=True, exist_ok=True)
    return selected


RESOURCE_ROOT = resolve_resource_root()
USER_DATA_DIR = ensure_user_data_dir()
PROGRESS_FILE = USER_DATA_DIR / "reader_config.json"


@dataclass(frozen=True)
class ReaderSettings:
    """Layout values kept together so a settings UI can be added later."""

    font_family: str = "SimSun"
    ui_font_family: str = "Microsoft YaHei"
    font_size: int = 14
    title_font_size: int = 16
    line_spacing: int = 9
    padding_x: int = 34
    padding_y: int = 24
    background_color: str = "#f7f3e9"
    foreground_color: str = "#292929"
    work_background_color: str = "#ffffff"
    work_foreground_color: str = "#202124"
    read_mode_delay_ms: int = 400
    progress_save_delay_ms: int = 700
    key_scroll_lines: int = 3


DEFAULT_SETTINGS = ReaderSettings()
