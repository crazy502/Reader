"""Responsive, cover-style bookshelf for the continuous reader."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import hashlib
from pathlib import Path
import tkinter as tk

from ..core.bookshelf import BookRecord, reading_percentage
from ..core.config import ReaderSettings
from ..i18n import tr


COVER_COLORS = (
    "#E9DDC7",  # 米白
    "#DCEAD5",  # 浅绿
    "#DCE8F2",  # 浅蓝
    "#F0DCDD",  # 浅粉
    "#F3E9C8",  # 淡黄
    "#E7DDF0",  # 淡紫
)
COVER_WIDTH = 132
COVER_HEIGHT = 172
CARD_WIDTH = COVER_WIDTH
CARD_HEIGHT = 218
GRID_GAP_X = 18
GRID_GAP_Y = 20
GRID_PADDING_X = 18
REFLOW_DELAY_MS = 70
MAX_COVER_TITLE_LENGTH = 24
MAX_CHAPTER_LENGTH = 13


def cover_color_for_book(book_id: str) -> str:
    """Map a book ID to a stable pastel color across Python processes."""
    digest = hashlib.sha256(book_id.encode("utf-8")).digest()
    return COVER_COLORS[int.from_bytes(digest[:2], "big") % len(COVER_COLORS)]


def display_cover_title(title: str) -> str:
    """Keep a long display title inside a fixed-size text cover."""
    compact = " ".join(title.split()) or tr("bookshelf_untitled")
    if len(compact) <= MAX_COVER_TITLE_LENGTH:
        return compact
    return f"{compact[: MAX_COVER_TITLE_LENGTH - 1]}…"


def display_book_progress(book: BookRecord) -> str:
    """Return the compact progress line shown below a cover."""
    chapter = book.chapter_title.strip() or tr(
        "bookshelf_chapter_index", index=book.chapter_index + 1
    )
    chapter = " ".join(chapter.split())
    if len(chapter) > MAX_CHAPTER_LENGTH:
        chapter = f"{chapter[: MAX_CHAPTER_LENGTH - 1]}…"
    return tr(
        "bookshelf_progress_line",
        progress=f"{reading_percentage(book):.0f}%",
        chapter=chapter,
    )


def column_count_for_width(width: int) -> int:
    """Calculate a compact grid width without allowing card overlap."""
    usable_width = max(1, width - GRID_PADDING_X * 2)
    return max(1, (usable_width + GRID_GAP_X) // (CARD_WIDTH + GRID_GAP_X))


class BookCard:
    """A fixed-size text cover whose primary action is continue reading."""

    def __init__(
        self,
        parent: tk.Misc,
        settings: ReaderSettings,
        book: BookRecord,
        active: bool,
        on_continue: Callable[[str], None],
        on_menu: Callable[[tk.Event[tk.Misc], str], None],
        on_menu_button: Callable[[tk.Misc, str], None],
        on_missing: Callable[[str], None],
    ) -> None:
        self.book_id = book.book_id
        self.is_missing = not Path(book.file_path).is_file()
        self.frame = tk.Frame(
            parent,
            width=CARD_WIDTH,
            height=CARD_HEIGHT,
            background=settings.background_color,
        )
        self.frame.pack_propagate(False)

        cover_color = cover_color_for_book(book.book_id)
        border_color = (
            settings.button_active_background_color if active else settings.border_color
        )
        self.cover = tk.Frame(
            self.frame,
            width=COVER_WIDTH,
            height=COVER_HEIGHT,
            background=cover_color,
            highlightbackground=border_color,
            highlightcolor=border_color,
            highlightthickness=2 if active else 1,
            cursor="hand2",
        )
        self.cover.pack(fill="x")
        self.cover.pack_propagate(False)

        self.title_label = tk.Label(
            self.cover,
            text=display_cover_title(book.display_title),
            justify="center",
            wraplength=COVER_WIDTH - 24,
            background=cover_color,
            foreground="#3B3833",
            font=(settings.ui_font_family, 11, "bold"),
            cursor="hand2",
        )
        self.title_label.place(relx=0.5, rely=0.48, anchor="center")

        self.menu_button = tk.Button(
            self.cover,
            text=tr("bookshelf_more"),
            command=lambda: on_menu_button(self.menu_button, book.book_id),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            background=cover_color,
            activebackground=cover_color,
            foreground="#726B62",
            activeforeground="#3B3833",
            font=(settings.ui_font_family, 11),
            cursor="arrow",
            padx=4,
            pady=0,
        )
        self.menu_button.place(relx=1.0, x=-5, y=4, anchor="ne")

        self.missing_label: tk.Label | None = None
        if self.is_missing:
            self.missing_label = tk.Label(
                self.cover,
                text=tr("bookshelf_card_missing"),
                background=cover_color,
                foreground="#8A4F46",
                font=(settings.ui_font_family, 8, "bold"),
                cursor="hand2",
            )
            self.missing_label.place(relx=0.5, rely=1.0, y=-12, anchor="s")

        self.progress_label = tk.Label(
            self.frame,
            text=display_book_progress(book),
            anchor="center",
            justify="center",
            background=settings.background_color,
            foreground=settings.secondary_foreground_color,
            font=(settings.ui_font_family, 9),
        )
        self.progress_label.pack(fill="x", pady=(7, 0))

        def activate(_event: tk.Event[tk.Misc]) -> None:
            if self.is_missing:
                on_missing(book.book_id)
            else:
                on_continue(book.book_id)

        clickable: list[tk.Misc] = [self.cover, self.title_label, self.progress_label]
        if self.missing_label is not None:
            clickable.append(self.missing_label)
        for widget in clickable:
            widget.bind("<Button-1>", activate)
            widget.bind(
                "<Button-3>",
                lambda event, selected=book.book_id: on_menu(event, selected),
            )

    def destroy(self) -> None:
        self.frame.destroy()


class BookshelfPage:
    """Display books as a persistent page inside the reader window."""

    def __init__(
        self,
        parent: tk.Misc,
        settings: ReaderSettings,
        books: Sequence[BookRecord],
        active_book_id: str | None,
        on_add: Callable[[], None],
        on_continue: Callable[[str], None],
        on_rename: Callable[[str], None],
        on_relocate: Callable[[str], None],
        on_remove: Callable[[str], None],
    ) -> None:
        self._settings = settings
        self._on_add = on_add
        self._on_continue = on_continue
        self._on_rename = on_rename
        self._on_relocate = on_relocate
        self._on_remove = on_remove
        self._reflow_after_id: str | None = None
        self._cards: dict[str, BookCard] = {}
        self._ordered_book_ids: list[str] = []
        self._column_count = 1
        self._context_menu: tk.Menu | None = None

        self.frame = tk.Frame(parent, background=settings.background_color)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        header = tk.Frame(
            self.frame,
            background=settings.toolbar_background_color,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        heading = tk.Label(
            header,
            text=tr("bookshelf_title"),
            anchor="w",
            background=settings.toolbar_background_color,
            foreground=settings.toolbar_foreground_color,
            font=(settings.ui_font_family, 14, "bold"),
        )
        heading.grid(row=0, column=0, sticky="ew", padx=(18, 8), pady=(14, 9))
        self.add_button = tk.Button(
            header,
            text=tr("bookshelf_add"),
            command=self._on_add,
            relief="flat",
            borderwidth=0,
            background=settings.toolbar_background_color,
            activebackground=settings.button_hover_background_color,
            foreground=settings.toolbar_foreground_color,
            activeforeground=settings.button_foreground_color,
            font=(settings.ui_font_family, 9),
        )
        self.add_button.grid(row=0, column=1, padx=(8, 18), pady=(11, 7))

        shelf_frame = tk.Frame(self.frame, background=settings.background_color)
        shelf_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 7), pady=(0, 12))
        shelf_frame.grid_rowconfigure(0, weight=1)
        shelf_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            shelf_frame,
            background=settings.background_color,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=36,
        )
        self.scrollbar = tk.Scrollbar(
            shelf_frame,
            orient="vertical",
            command=self.canvas.yview,
            background=settings.scrollbar_thumb_color,
            activebackground=settings.button_active_background_color,
            troughcolor=settings.scrollbar_trough_color,
            highlightbackground=settings.border_color,
            highlightcolor=settings.border_color,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.content = tk.Frame(self.canvas, background=settings.background_color)
        self._content_window = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw"
        )
        self.content.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._schedule_reflow)
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.content)

        self.missing_prompt = tk.Frame(
            self.frame,
            background=settings.toolbar_background_color,
            highlightbackground=settings.border_color,
            highlightthickness=1,
        )
        self.missing_prompt.grid_columnconfigure(0, weight=1)
        prompt_label = tk.Label(
            self.missing_prompt,
            text=tr("bookshelf_missing_prompt"),
            anchor="w",
            background=settings.toolbar_background_color,
            foreground=settings.toolbar_foreground_color,
            font=(settings.ui_font_family, 9),
        )
        prompt_label.grid(row=0, column=0, sticky="ew", padx=10, pady=7)
        self.relocate_button = tk.Button(
            self.missing_prompt,
            text=tr("bookshelf_relocate"),
            relief="flat",
            borderwidth=0,
            background=settings.button_background_color,
            activebackground=settings.button_hover_background_color,
            foreground=settings.button_foreground_color,
            font=(settings.ui_font_family, 9),
        )
        self.relocate_button.grid(row=0, column=1, padx=(8, 4), pady=4)
        cancel_button = tk.Button(
            self.missing_prompt,
            text=tr("cancel"),
            command=self._hide_missing_prompt,
            relief="flat",
            borderwidth=0,
            background=settings.toolbar_background_color,
            activebackground=settings.button_hover_background_color,
            foreground=settings.secondary_foreground_color,
            font=(settings.ui_font_family, 9),
        )
        cancel_button.grid(row=0, column=2, padx=(4, 8), pady=4)

        self.empty_label = tk.Label(
            self.content,
            text=tr("bookshelf_empty"),
            justify="center",
            background=settings.background_color,
            foreground=settings.secondary_foreground_color,
            font=(settings.ui_font_family, 10),
        )

        self.refresh(books, active_book_id)

    @property
    def column_count(self) -> int:
        return self._column_count

    def refresh(
        self, books: Sequence[BookRecord], active_book_id: str | None
    ) -> None:
        scroll_position = self.canvas.yview()[0] if self._cards else 0.0
        self._hide_missing_prompt()
        self.empty_label.grid_forget()
        for card in self._cards.values():
            card.destroy()
        self._cards.clear()
        self._ordered_book_ids = []

        for book in books:
            card = BookCard(
                self.content,
                self._settings,
                book,
                book.book_id == active_book_id,
                self._on_continue,
                self._show_context_menu,
                self._show_context_menu_from_button,
                self._show_missing_prompt,
            )
            self._cards[book.book_id] = card
            self._ordered_book_ids.append(book.book_id)
            self._bind_card_mousewheel(card)

        if not self._cards:
            self.empty_label.grid(row=0, column=0, padx=24, pady=70)
        self._reflow_cards()
        self.frame.after_idle(lambda: self.canvas.yview_moveto(scroll_position))

    def focus(self) -> None:
        if self.frame.winfo_exists():
            self.canvas.focus_set()

    def show(self) -> None:
        self.frame.pack(fill="both", expand=True)
        self.frame.after_idle(self._reflow_cards)

    def hide(self) -> None:
        self.frame.pack_forget()

    def destroy(self) -> None:
        if self._reflow_after_id is not None:
            self.frame.after_cancel(self._reflow_after_id)
            self._reflow_after_id = None
        self.frame.destroy()

    def _schedule_reflow(self, event: tk.Event[tk.Misc]) -> None:
        self.canvas.itemconfigure(self._content_window, width=max(1, event.width))
        if self._reflow_after_id is not None:
            self.frame.after_cancel(self._reflow_after_id)
        self._reflow_after_id = self.frame.after(
            REFLOW_DELAY_MS, self._reflow_cards
        )

    def _reflow_cards(self) -> None:
        self._reflow_after_id = None
        width = max(1, self.canvas.winfo_width())
        self._column_count = column_count_for_width(width)
        for card in self._cards.values():
            card.frame.grid_forget()
        if not self._cards:
            self._update_scroll_region()
            return

        used_width = (
            self._column_count * CARD_WIDTH
            + max(0, self._column_count - 1) * GRID_GAP_X
        )
        left_padding = max(GRID_PADDING_X, (width - used_width) // 2)
        for index, book_id in enumerate(self._ordered_book_ids):
            row, column = divmod(index, self._column_count)
            horizontal_padding = (left_padding if column == 0 else GRID_GAP_X, 0)
            self._cards[book_id].frame.grid(
                row=row,
                column=column,
                padx=horizontal_padding,
                pady=(0, GRID_GAP_Y),
                sticky="n",
            )
        self.content.update_idletasks()
        self._update_scroll_region()

    def _update_scroll_region(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all") or (0, 0, 0, 0))

    def _on_mousewheel(self, event: tk.Event[tk.Misc]) -> str:
        if event.delta:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _bind_mousewheel(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel)

    def _bind_card_mousewheel(self, card: BookCard) -> None:
        widgets: list[tk.Misc] = [
            card.frame,
            card.cover,
            card.title_label,
            card.menu_button,
            card.progress_label,
        ]
        if card.missing_label is not None:
            widgets.append(card.missing_label)
        for widget in widgets:
            self._bind_mousewheel(widget)

    def _show_missing_prompt(self, book_id: str) -> None:
        self.relocate_button.configure(
            command=lambda selected=book_id: self._relocate_missing(selected)
        )
        self.missing_prompt.grid(
            row=2, column=0, sticky="ew", padx=18, pady=(0, 12)
        )

    def _hide_missing_prompt(self) -> None:
        self.missing_prompt.grid_forget()

    def _relocate_missing(self, book_id: str) -> None:
        self._hide_missing_prompt()
        self._on_relocate(book_id)

    def _show_context_menu(
        self, event: tk.Event[tk.Misc], book_id: str
    ) -> None:
        self._post_context_menu(book_id, event.x_root, event.y_root)

    def _show_context_menu_from_button(self, widget: tk.Misc, book_id: str) -> None:
        self._post_context_menu(
            book_id,
            widget.winfo_rootx(),
            widget.winfo_rooty() + widget.winfo_height(),
        )

    def _post_context_menu(self, book_id: str, x: int, y: int) -> None:
        menu = tk.Menu(self.frame, tearoff=False)
        menu.add_command(
            label=tr("bookshelf_rename"),
            command=lambda: self._on_rename(book_id),
        )
        menu.add_command(
            label=tr("bookshelf_relocate"),
            command=lambda: self._on_relocate(book_id),
        )
        menu.add_separator()
        menu.add_command(
            label=tr("bookshelf_remove"),
            command=lambda: self._on_remove(book_id),
        )
        self._context_menu = menu
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()
