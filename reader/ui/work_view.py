"""Work-note view shown while reading content is hidden."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk

from ..core.config import ReaderSettings
from ..i18n import tr


class WorkView:
    """Own the work-mode note widgets."""

    def __init__(
        self,
        parent: tk.Misc,
        settings: ReaderSettings,
        on_note_changed: Callable[[], None],
        on_enable_hover_reading: Callable[[], None],
    ) -> None:
        self.frame = tk.Frame(parent, background=settings.work_background_color)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        toolbar = tk.Frame(
            self.frame,
            background=settings.work_toolbar_background_color,
        )
        toolbar.grid(row=0, column=0, sticky="ew")
        title = tk.Label(
            toolbar,
            text=tr("work_title"),
            anchor="w",
            background=settings.work_toolbar_background_color,
            foreground=settings.work_foreground_color,
            font=(settings.work_font_family, settings.work_font_size, "bold"),
        )
        title.pack(fill="x", padx=12, pady=8)

        editor_frame = tk.Frame(self.frame, background=settings.work_background_color)
        editor_frame.grid(row=1, column=0, sticky="nsew")
        scrollbar = tk.Scrollbar(editor_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.text = tk.Text(
            editor_frame,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            background=settings.work_background_color,
            foreground=settings.work_foreground_color,
            insertbackground=settings.work_foreground_color,
            selectbackground="#C8DCF0",
            selectforeground=settings.work_foreground_color,
            font=(settings.work_font_family, settings.work_font_size),
            padx=12,
            pady=12,
            yscrollcommand=scrollbar.set,
        )
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.text.yview)

        status_bar = tk.Frame(
            self.frame,
            background=settings.work_toolbar_background_color,
        )
        status_bar.grid(row=2, column=0, sticky="ew")
        hint = tk.Label(
            status_bar,
            text=tr("work_hint"),
            anchor="w",
            background=settings.work_toolbar_background_color,
            foreground=settings.work_secondary_foreground_color,
            font=(settings.work_font_family, 9),
        )
        hint.pack(side="left", padx=10, pady=6)
        enable_hover_button = tk.Button(
            status_bar,
            text=tr("enable_hover_reading"),
            command=on_enable_hover_reading,
            relief="flat",
            borderwidth=0,
            background=settings.work_toolbar_background_color,
            foreground=settings.work_secondary_foreground_color,
            activebackground=settings.work_button_hover_color,
            activeforeground=settings.work_foreground_color,
            font=(settings.work_font_family, 9),
        )
        enable_hover_button.pack(side="right", padx=8, pady=3)

        self.text.bind("<<Modified>>", lambda _event: self._on_modified(on_note_changed))
        self.text.bind("<Control-a>", self._select_all)

    def set_note(self, content: str) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.edit_modified(False)

    def get_note(self) -> str:
        return self.text.get("1.0", "end-1c")

    def focus(self) -> None:
        self.text.focus_set()

    def _on_modified(self, callback: Callable[[], None]) -> None:
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        callback()

    def _select_all(self, _event: tk.Event[tk.Misc]) -> str:
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "end-1c")
        self.text.see("insert")
        return "break"

    def show(self) -> None:
        self.frame.pack(fill="both", expand=True)

    def hide(self) -> None:
        self.frame.pack_forget()
