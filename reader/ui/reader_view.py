"""Continuous reading widgets and Text view operations."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk

from ..core.config import ReaderSettings
from ..core.novel_parser import Novel
from ..i18n import tr


class ReaderView:
    """Own the toolbar and continuous Text-based reading surface."""

    def __init__(
        self,
        parent: tk.Misc,
        settings: ReaderSettings,
        on_open_file: Callable[[], None],
        on_open_chapters: Callable[[], None],
        on_scrollbar: Callable[..., None],
    ) -> None:
        self.settings = settings

        self.toolbar = tk.Frame(parent, background=settings.background_color)
        self.toolbar.pack(fill="x", padx=settings.padding_x, pady=(12, 0))
        self.open_button = tk.Button(
            self.toolbar,
            text=tr("open_file"),
            command=on_open_file,
            font=(settings.ui_font_family, 10),
        )
        self.open_button.pack(side="left")
        self.chapter_button = tk.Button(
            self.toolbar,
            text=tr("chapter_navigation"),
            command=on_open_chapters,
            anchor="w",
            relief="flat",
            borderwidth=0,
            background=settings.background_color,
            activebackground=settings.background_color,
            foreground=settings.foreground_color,
            font=(settings.ui_font_family, 10, "bold"),
            state="disabled",
        )
        self.chapter_button.pack(side="left", padx=(12, 0))
        self.status = tk.Label(
            self.toolbar,
            text=tr("status_no_book"),
            anchor="e",
            background=settings.background_color,
            foreground="#606060",
            font=(settings.ui_font_family, 9),
        )
        self.status.pack(side="right", fill="x", expand=True, padx=(16, 0))

        self.frame = tk.Frame(parent, background=settings.background_color)
        text_frame = tk.Frame(self.frame, background=settings.background_color)
        text_frame.pack(fill="both", expand=True, pady=(12, 0))
        self.scrollbar = tk.Scrollbar(text_frame, orient="vertical", command=on_scrollbar)
        self.scrollbar.pack(side="right", fill="y")
        self.text = tk.Text(
            text_frame,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            background=settings.background_color,
            foreground=settings.foreground_color,
            font=(settings.font_family, settings.font_size),
            padx=settings.padding_x,
            pady=settings.padding_y,
            spacing3=settings.line_spacing,
            cursor="arrow",
            state="disabled",
            yscrollcommand=self.scrollbar.set,
        )
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure(
            "chapter-title",
            font=(settings.ui_font_family, settings.title_font_size, "bold"),
            spacing1=12,
            spacing3=12,
        )
        hint_label = tk.Label(
            self.frame,
            text=tr("shortcut_hint"),
            anchor="w",
            background=settings.background_color,
            foreground="#777777",
            font=(settings.ui_font_family, 9),
        )
        hint_label.pack(fill="x", padx=settings.padding_x, pady=(6, 10))

    def bind_reading_events(
        self,
        on_key_scroll: Callable[[tk.Event[tk.Misc], int], str],
        on_mouse_wheel: Callable[[tk.Event[tk.Misc]], None],
    ) -> None:
        self.text.bind("<Up>", lambda event: on_key_scroll(event, -1))
        self.text.bind("<Down>", lambda event: on_key_scroll(event, 1))
        # Do not consume MouseWheel: Tk's Text class performs the natural scroll.
        self.text.bind("<MouseWheel>", on_mouse_wheel, add="+")

    def install_novel(self, novel: Novel) -> None:
        self.status.configure(text=tr("status_loaded", name=novel.path.name))
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", novel.text)
        for chapter in novel.chapters:
            start = f"{chapter.start_line}.0"
            end = f"{chapter.start_line}.{len(chapter.title)}"
            self.text.tag_add("chapter-title", start, end)
        self.text.configure(state="disabled")

    def set_chapter_title(self, title: str) -> None:
        display_title = title.strip()
        if len(display_title) > 38:
            display_title = f"{display_title[:37]}…"
        self.chapter_button.configure(
            text=tr("chapter_button", title=display_title),
            state="normal",
        )

    def jump_to_char(self, char_position: int) -> None:
        index = f"1.0 + {max(0, char_position)} chars"
        self.text.mark_set("insert", index)
        self.text.yview(index)

    def top_char_position(self) -> int:
        top_index = self.text.index("@0,0")
        count = self.text.count("1.0", top_index, "chars")
        return 0 if not count else int(count[0])

    def scroll_lines(self, line_count: int) -> None:
        self.text.yview_scroll(line_count, "units")

    def scroll(self, *arguments: str) -> None:
        self.text.yview(*arguments)

    def is_mapped(self) -> bool:
        return bool(self.text.winfo_ismapped())

    def show(self) -> None:
        self.toolbar.pack(fill="x", padx=self.settings.padding_x, pady=(12, 0))
        self.frame.pack(fill="both", expand=True)

    def hide_body(self) -> None:
        self.frame.pack_forget()

    def hide_toolbar(self) -> None:
        self.toolbar.pack_forget()

    def focus(self) -> None:
        self.text.focus_set()
