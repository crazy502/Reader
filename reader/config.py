"""Application configuration and filesystem locations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
PROGRESS_FILE = DATA_DIR / "reader_config.json"


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
