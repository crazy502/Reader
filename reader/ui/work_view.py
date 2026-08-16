"""Work-note view shown while reading content is hidden."""

from __future__ import annotations

import tkinter as tk

from ..core.config import ReaderSettings
from ..i18n import tr


class WorkView:
    """Own the work-mode note widgets."""

    def __init__(self, parent: tk.Misc, settings: ReaderSettings) -> None:
        self.frame = tk.Frame(parent, background=settings.work_background_color)
        title = tk.Label(
            self.frame,
            text=tr("work_title"),
            anchor="w",
            background=settings.work_background_color,
            foreground=settings.work_foreground_color,
            font=(settings.ui_font_family, 16, "bold"),
        )
        title.pack(fill="x", padx=settings.padding_x, pady=(38, 18))
        body = tk.Label(
            self.frame,
            text=tr("work_body"),
            anchor="nw",
            justify="left",
            background=settings.work_background_color,
            foreground=settings.work_foreground_color,
            font=(settings.ui_font_family, 12),
        )
        body.pack(fill="both", expand=True, padx=settings.padding_x)
        hint = tk.Label(
            self.frame,
            text=tr("work_hint"),
            anchor="w",
            background=settings.work_background_color,
            foreground="#777777",
            font=(settings.ui_font_family, 9),
        )
        hint.pack(fill="x", padx=settings.padding_x, pady=18)

    def show(self) -> None:
        self.frame.pack(fill="both", expand=True)

    def hide(self) -> None:
        self.frame.pack_forget()
