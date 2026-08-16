"""Application configuration and filesystem locations."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


APP_NAME = "Reader"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

BODY_BG = "#F6F1E7"
BODY_FG = "#2B2A28"
TOOLBAR_BG = "#EEE7DA"
TOOLBAR_FG = "#4A4640"
SECONDARY_FG = "#8A8278"
BUTTON_BG = "#E3DACB"
BUTTON_HOVER_BG = "#D8CEBE"
BUTTON_ACTIVE_BG = "#CCC0AE"
BUTTON_FG = "#403C37"
INPUT_BG = "#FBF8F1"
BORDER = "#D6CCBD"
CHAPTER_ACTIVE_BG = "#DED4C4"
CHAPTER_ACTIVE_FG = "#2F2C28"
CHAPTER_LIST_BG = "#F7F2E9"
CHAPTER_LIST_FG = "#373431"
SCROLLBAR_TROUGH = "#EEE8DE"
SCROLLBAR_THUMB = "#C9BFAF"


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
    background_color: str = BODY_BG
    foreground_color: str = BODY_FG
    toolbar_background_color: str = TOOLBAR_BG
    toolbar_foreground_color: str = TOOLBAR_FG
    secondary_foreground_color: str = SECONDARY_FG
    button_background_color: str = BUTTON_BG
    button_hover_background_color: str = BUTTON_HOVER_BG
    button_active_background_color: str = BUTTON_ACTIVE_BG
    button_foreground_color: str = BUTTON_FG
    input_background_color: str = INPUT_BG
    border_color: str = BORDER
    chapter_active_background_color: str = CHAPTER_ACTIVE_BG
    chapter_active_foreground_color: str = CHAPTER_ACTIVE_FG
    chapter_list_background_color: str = CHAPTER_LIST_BG
    chapter_list_foreground_color: str = CHAPTER_LIST_FG
    scrollbar_trough_color: str = SCROLLBAR_TROUGH
    scrollbar_thumb_color: str = SCROLLBAR_THUMB
    work_background_color: str = BODY_BG
    work_foreground_color: str = BODY_FG
    read_mode_delay_ms: int = 400
    progress_save_delay_ms: int = 700
    key_scroll_lines: int = 3


DEFAULT_SETTINGS = ReaderSettings()
