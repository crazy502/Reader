"""Lightweight chapter directory for the continuous reader."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Sequence
import tkinter as tk
import unicodedata

from ..core.novel_parser import Chapter
from ..i18n import tr


def chapter_index_for_position(chapter_starts: Sequence[int], char_position: int) -> int:
    """Return the chapter containing a character position using binary search."""
    if not chapter_starts:
        return 0
    return max(0, bisect_right(chapter_starts, char_position) - 1)


def matching_chapter_indices(chapters: Sequence[Chapter], query: str) -> list[int]:
    """Return title matches in their original chapter order."""
    needle = _normalize_search_text(query)
    if not needle:
        return list(range(len(chapters)))
    return [
        index
        for index, chapter in enumerate(chapters)
        if needle in _normalize_search_text(chapter.title)
    ]


def _normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(normalized.split())


def _display_chapter_title(title: str) -> str:
    stripped = title.strip()
    return stripped if len(stripped) <= 38 else f"{stripped[:37]}…"


class ChapterDirectory:
    """Scrollable, searchable chapter picker hosted in a temporary Toplevel."""

    def __init__(
        self,
        parent: tk.Misc,
        chapters: Sequence[Chapter],
        current_index: int,
        on_select: Callable[[int], None],
        on_close: Callable[[], None],
    ) -> None:
        self._chapters = chapters
        self._current_index = current_index
        self._on_select = on_select
        self._on_close = on_close
        self._filtered_indices: list[int] = []
        self._refreshing = False
        self._closed = False

        self.window = tk.Toplevel(parent)
        self.window.title(tr("chapter_directory_title"))
        self.window.transient(parent)
        self.window.configure(background="#f7f3e9")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", lambda _event: self.close())
        self._place_near_parent(parent)

        heading = tk.Label(
            self.window,
            text=tr("chapter_directory_title"),
            anchor="w",
            background="#f7f3e9",
            foreground="#292929",
            font=("Microsoft YaHei", 14, "bold"),
        )
        heading.pack(fill="x", padx=18, pady=(16, 10))

        search_frame = tk.Frame(self.window, background="#f7f3e9")
        search_frame.pack(fill="x", padx=18, pady=(0, 10))
        search_label = tk.Label(
            search_frame,
            text=tr("chapter_search_label"),
            background="#f7f3e9",
            foreground="#555555",
            font=("Microsoft YaHei", 10),
        )
        search_label.pack(side="left", padx=(0, 8))
        self.search_text = tk.StringVar()
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_text,
            relief="solid",
            borderwidth=1,
            font=("Microsoft YaHei", 10),
        )
        self.search_entry.pack(side="left", fill="x", expand=True)

        list_frame = tk.Frame(self.window, background="#f7f3e9")
        list_frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.chapter_items = tk.StringVar(value=())
        self.chapter_list = tk.Listbox(
            list_frame,
            listvariable=self.chapter_items,
            activestyle="none",
            background="#fffdf7",
            foreground="#292929",
            selectbackground="#d7e8f5",
            selectforeground="#202124",
            exportselection=False,
            relief="solid",
            borderwidth=1,
            font=("Microsoft YaHei", 10),
            yscrollcommand=scrollbar.set,
        )
        self.chapter_list.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.chapter_list.yview)

        self.search_text.trace_add("write", self._on_search_changed)
        self.chapter_list.bind("<ButtonRelease-1>", self._on_chapter_clicked)
        self.chapter_list.bind("<Return>", self._on_selected_chapter_confirmed)
        self._refresh_list(center_current=True)
        self.window.grab_set()
        self.search_entry.focus_set()

    def focus(self) -> None:
        if self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.search_entry.focus_set()

    def contains_screen_point(self, x: int, y: int) -> bool:
        if self._closed or not self.window.winfo_exists():
            return False
        left = self.window.winfo_rootx()
        top = self.window.winfo_rooty()
        return (
            left <= x < left + self.window.winfo_width()
            and top <= y < top + self.window.winfo_height()
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self.window.grab_current() is self.window:
                self.window.grab_release()
            self.window.destroy()
        finally:
            self._on_close()

    def _place_near_parent(self, parent: tk.Misc) -> None:
        parent.update_idletasks()
        parent_width = max(1, parent.winfo_width())
        parent_height = max(1, parent.winfo_height())
        width = min(460, max(320, parent_width - 40))
        height = min(520, max(280, parent_height - 40))
        x = parent.winfo_rootx() + max(0, (parent_width - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent_height - height) // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.minsize(300, 260)

    def _on_search_changed(self, *_arguments: str) -> None:
        self._refresh_list(center_current=False)

    def _refresh_list(self, center_current: bool) -> None:
        self._refreshing = True
        try:
            self._filtered_indices = matching_chapter_indices(
                self._chapters, self.search_text.get()
            )
            self.chapter_items.set(
                tuple(
                    _display_chapter_title(self._chapters[index].title)
                    for index in self._filtered_indices
                )
            )

            if self._current_index not in self._filtered_indices:
                if self._filtered_indices:
                    self.chapter_list.yview(0)
                return

            row = self._filtered_indices.index(self._current_index)
            self.chapter_list.selection_set(row)
            self.chapter_list.activate(row)
            if center_current:
                self.window.update_idletasks()
                first_row_box = self.chapter_list.bbox(0)
                row_height = max(1, first_row_box[3] if first_row_box else 20)
                visible_rows = max(1, self.chapter_list.winfo_height() // row_height)
                self.chapter_list.yview(max(0, row - visible_rows // 2))
            else:
                self.chapter_list.see(row)
        finally:
            self._refreshing = False

    def _on_chapter_clicked(self, event: tk.Event[tk.Misc]) -> None:
        if self._refreshing or not self._filtered_indices:
            return
        row = self.chapter_list.nearest(event.y)
        row_box = self.chapter_list.bbox(row)
        if row_box is None or not row_box[1] <= event.y < row_box[1] + row_box[3]:
            return
        self.chapter_list.selection_clear(0, "end")
        self.chapter_list.selection_set(row)
        self._select_row(row)

    def _on_selected_chapter_confirmed(self, _event: tk.Event[tk.Misc]) -> None:
        selection = self.chapter_list.curselection()
        if not selection:
            return
        self._select_row(int(selection[0]))

    def _select_row(self, row: int) -> None:
        chapter_index = self._filtered_indices[row]
        self.close()
        self._on_select(chapter_index)
