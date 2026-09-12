"""Continuous reading widgets and Text view operations."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk

from ..core.config import (
    READING_THEMES,
    ReaderSettings,
    get_reading_theme,
    normalize_reading_theme,
)
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
        reading_theme: str,
        on_reading_theme_changed: Callable[[str], None],
    ) -> None:
        self.settings = settings

        self.toolbar = tk.Frame(parent, background=settings.toolbar_background_color)
        self.toolbar.pack(fill="x", padx=settings.padding_x, pady=(12, 0))
        self.open_button = tk.Button(
            self.toolbar,
            text=tr("open_file"),
            command=on_open_file,
            font=(settings.ui_font_family, 10),
            background=settings.button_background_color,
            foreground=settings.button_foreground_color,
            activebackground=settings.button_hover_background_color,
            activeforeground=settings.button_foreground_color,
            highlightbackground=settings.border_color,
            highlightcolor=settings.border_color,
        )
        self.open_button.pack(side="left")
        self.chapter_button = tk.Button(
            self.toolbar,
            text=tr("chapter_navigation"),
            command=on_open_chapters,
            anchor="w",
            relief="flat",
            borderwidth=0,
            background=settings.button_background_color,
            activebackground=settings.button_hover_background_color,
            foreground=settings.button_foreground_color,
            activeforeground=settings.button_foreground_color,
            disabledforeground=settings.secondary_foreground_color,
            highlightbackground=settings.border_color,
            highlightcolor=settings.border_color,
            font=(settings.ui_font_family, 10, "bold"),
            state="disabled",
        )
        self.chapter_button.pack(side="left", padx=(12, 0))
        self._reading_theme = tk.StringVar(value=normalize_reading_theme(reading_theme))
        self.theme_button = tk.Menubutton(
            self.toolbar,
            text=tr("reading_theme"),
            relief="flat",
            borderwidth=0,
            background=settings.button_background_color,
            activebackground=settings.button_hover_background_color,
            foreground=settings.button_foreground_color,
            activeforeground=settings.button_foreground_color,
            highlightbackground=settings.border_color,
            highlightcolor=settings.border_color,
            font=(settings.ui_font_family, 10),
        )
        theme_menu = tk.Menu(self.theme_button, tearoff=False)
        for theme_name in READING_THEMES:
            theme_menu.add_radiobutton(
                label=tr(f"reading_theme_{theme_name}"),
                value=theme_name,
                variable=self._reading_theme,
                command=lambda selected=theme_name: on_reading_theme_changed(selected),
            )
        self.theme_button.configure(menu=theme_menu)
        self.theme_button.pack(side="left", padx=(12, 0))
        self.status = tk.Label(
            self.toolbar,
            text=tr("status_no_book"),
            anchor="e",
            background=settings.toolbar_background_color,
            foreground=settings.secondary_foreground_color,
            font=(settings.ui_font_family, 9),
        )
        self.status.pack(side="right", fill="x", expand=True, padx=(16, 0))

        self.frame = tk.Frame(parent, background=settings.background_color)
        self.text_frame = tk.Frame(self.frame, background=settings.background_color)
        self.text_frame.pack(fill="both", expand=True, pady=(12, 0))
        self.scrollbar = tk.Scrollbar(
            self.text_frame,
            orient="vertical",
            command=on_scrollbar,
            background=settings.scrollbar_thumb_color,
            activebackground=settings.button_active_background_color,
            troughcolor=settings.scrollbar_trough_color,
            highlightbackground=settings.border_color,
            highlightcolor=settings.border_color,
        )
        self.scrollbar.pack(side="right", fill="y")
        self.text = tk.Text(
            self.text_frame,
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
            foreground=settings.foreground_color,
            spacing1=12,
            spacing3=12,
        )
        self.hint_label = tk.Label(
            self.frame,
            text=tr("shortcut_hint"),
            anchor="w",
            background=settings.background_color,
            foreground=settings.secondary_foreground_color,
            font=(settings.ui_font_family, 9),
        )
        self.hint_label.pack(fill="x", padx=settings.padding_x, pady=(6, 10))
        self.apply_reading_theme(reading_theme)

    def apply_reading_theme(self, theme_name: str) -> None:
        """Apply a fixed color pair only to the continuous reading surface."""
        normalized = normalize_reading_theme(theme_name)
        theme = get_reading_theme(normalized)
        self._reading_theme.set(normalized)
        self.frame.configure(background=theme.background)
        self.text_frame.configure(background=theme.background)
        self.text.configure(background=theme.background, foreground=theme.foreground)
        self.text.tag_configure("chapter-title", foreground=theme.foreground)
        self.hint_label.configure(background=theme.background)
        self.scrollbar.configure(troughcolor=theme.background)

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
