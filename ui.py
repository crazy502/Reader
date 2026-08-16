"""Tkinter UI for continuous TXT reading and work-mode switching."""

from __future__ import annotations

from bisect import bisect_right
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from config import DEFAULT_SETTINGS, PROGRESS_FILE, ReaderSettings
from novel_parser import Novel, NovelLoadError, parse_novel
from progress import ReadingProgress, load_progress, save_progress
from src.i18n import tr


READ_MODE = "read"
WORK_MODE = "work"


class ReaderApp:
    """Display one continuous novel and persist the top visible character."""

    def __init__(self, root: tk.Tk, settings: ReaderSettings = DEFAULT_SETTINGS) -> None:
        self.root = root
        self.settings = settings
        self.novel: Novel | None = None
        self.mode = WORK_MODE
        self._read_after_id: str | None = None
        self._save_after_id: str | None = None
        self._pointer_inside: bool | None = None
        self._suspend_progress_tracking = False
        self._progress_dirty = False
        self._chapter_starts: tuple[int, ...] = ()
        self._pending_char_position: int | None = None
        self._build_window()
        self._build_widgets()
        self._bind_events()
        self.show_work_mode()
        self.root.after(100, self.restore_last_progress)
        self.root.after(120, self._poll_pointer)

    def _build_window(self) -> None:
        self.root.title(tr("app_title"))
        self.root.geometry("760x620")
        self.root.minsize(470, 360)
        self.root.configure(background=self.settings.background_color)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_widgets(self) -> None:
        self.container = tk.Frame(self.root, background=self.settings.background_color)
        self.container.pack(fill="both", expand=True)

        self.toolbar = tk.Frame(self.container, background=self.settings.background_color)
        self.toolbar.pack(fill="x", padx=self.settings.padding_x, pady=(12, 0))
        self.open_button = tk.Button(
            self.toolbar,
            text=tr("open_file"),
            command=self.choose_file,
            font=(self.settings.ui_font_family, 10),
        )
        self.open_button.pack(side="left")
        self.status = tk.Label(
            self.toolbar,
            text=tr("status_no_book"),
            anchor="e",
            background=self.settings.background_color,
            foreground="#606060",
            font=(self.settings.ui_font_family, 9),
        )
        self.status.pack(side="right", fill="x", expand=True, padx=(16, 0))

        self.read_frame = tk.Frame(self.container, background=self.settings.background_color)
        self.text_frame = tk.Frame(self.read_frame, background=self.settings.background_color)
        self.text_frame.pack(fill="both", expand=True, pady=(12, 0))
        self.scrollbar = tk.Scrollbar(self.text_frame, orient="vertical", command=self._scrollbar_command)
        self.scrollbar.pack(side="right", fill="y")
        self.text = tk.Text(
            self.text_frame,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            background=self.settings.background_color,
            foreground=self.settings.foreground_color,
            font=(self.settings.font_family, self.settings.font_size),
            padx=self.settings.padding_x,
            pady=self.settings.padding_y,
            spacing3=self.settings.line_spacing,
            cursor="arrow",
            state="disabled",
            yscrollcommand=self.scrollbar.set,
        )
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure(
            "chapter-title",
            font=(self.settings.ui_font_family, self.settings.title_font_size, "bold"),
            spacing1=12,
            spacing3=12,
        )
        self.hint_label = tk.Label(
            self.read_frame,
            text=tr("shortcut_hint"),
            anchor="w",
            background=self.settings.background_color,
            foreground="#777777",
            font=(self.settings.ui_font_family, 9),
        )
        self.hint_label.pack(fill="x", padx=self.settings.padding_x, pady=(6, 10))

        self.work_frame = tk.Frame(self.container, background=self.settings.work_background_color)
        self.work_title = tk.Label(
            self.work_frame,
            text=tr("work_title"),
            anchor="w",
            background=self.settings.work_background_color,
            foreground=self.settings.work_foreground_color,
            font=(self.settings.ui_font_family, 16, "bold"),
        )
        self.work_title.pack(fill="x", padx=self.settings.padding_x, pady=(38, 18))
        self.work_body = tk.Label(
            self.work_frame,
            text=tr("work_body"),
            anchor="nw",
            justify="left",
            background=self.settings.work_background_color,
            foreground=self.settings.work_foreground_color,
            font=(self.settings.ui_font_family, 12),
        )
        self.work_body.pack(fill="both", expand=True, padx=self.settings.padding_x)
        self.work_hint = tk.Label(
            self.work_frame,
            text=tr("work_hint"),
            anchor="w",
            background=self.settings.work_background_color,
            foreground="#777777",
            font=(self.settings.ui_font_family, 9),
        )
        self.work_hint.pack(fill="x", padx=self.settings.padding_x, pady=18)

    def _bind_events(self) -> None:
        self.text.bind("<Up>", lambda event: self._scroll_with_key(event, -1))
        self.text.bind("<Down>", lambda event: self._scroll_with_key(event, 1))
        self.root.bind("<Up>", lambda event: self._scroll_with_key(event, -1))
        self.root.bind("<Down>", lambda event: self._scroll_with_key(event, 1))
        # Do not consume MouseWheel: Tk's Text class performs the natural scroll.
        self.text.bind("<MouseWheel>", self._on_mouse_wheel_activity, add="+")
        self.root.bind_all("<Alt-q>", self._boss_key, add="+")

    def choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            title=tr("open_file"),
            filetypes=[(tr("file_types"), "*.txt"), (tr("all_files"), "*.*")],
        )
        if selected:
            self.open_novel(Path(selected))

    def open_novel(self, path: Path) -> bool:
        self.save_current_progress()
        novel = self._parse_path(path)
        if novel is None:
            return False
        self._install_novel(novel, 0)
        self.show_read_mode()
        self.save_current_progress()
        return True

    def _parse_path(self, path: Path) -> Novel | None:
        try:
            novel = parse_novel(path)
            if not any(chapter.content.strip() for chapter in novel.chapters):
                messagebox.showwarning(tr("empty_file_title"), tr("empty_file"), parent=self.root)
                return None
            return novel
        except (OSError, NovelLoadError, UnicodeError):
            messagebox.showerror(tr("load_error_title"), tr("load_error"), parent=self.root)
            return None

    def _install_novel(self, novel: Novel, char_position: int) -> None:
        self.novel = novel
        self._chapter_starts = tuple(chapter.start_char for chapter in novel.chapters)
        self.status.configure(text=tr("status_loaded", name=novel.path.name))
        self._suspend_progress_tracking = True
        try:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", novel.text)
            for chapter in novel.chapters:
                start = f"{chapter.start_line}.0"
                end = f"{chapter.start_line}.{len(chapter.title)}"
                self.text.tag_add("chapter-title", start, end)
            self.text.configure(state="disabled")
            self._pending_char_position = min(max(0, char_position), len(novel.text))
            if self.text.winfo_ismapped():
                self._jump_to_pending_position()
        finally:
            self._suspend_progress_tracking = False
        self._progress_dirty = False

    def _text_index(self, char_position: int) -> str:
        return f"1.0 + {max(0, char_position)} chars"

    def _jump_to_char(self, char_position: int) -> None:
        if self.novel is None:
            return
        position = min(max(0, char_position), len(self.novel.text))
        index = self._text_index(position)
        self.text.mark_set("insert", index)
        self.text.yview(index)
        self.root.update_idletasks()

    def _jump_to_pending_position(self) -> None:
        if self._pending_char_position is None:
            return
        position = self._pending_char_position
        self._pending_char_position = None
        self._jump_to_char(position)

    def jump_to_chapter(self, index: int) -> None:
        """Jump to a chapter heading and immediately persist the location."""
        if self.novel is None or not self.novel.chapters:
            return
        chapter_index = min(max(0, index), len(self.novel.chapters) - 1)
        self._suspend_progress_tracking = True
        try:
            self._jump_to_char(self.novel.chapters[chapter_index].start_char)
        finally:
            self._suspend_progress_tracking = False
        self._progress_dirty = True
        self.save_current_progress()

    def _scroll_with_key(self, _event: tk.Event[tk.Misc], direction: int) -> str:
        if self.mode == READ_MODE and self.novel is not None:
            self.text.yview_scroll(direction * self.settings.key_scroll_lines, "units")
            self._mark_progress_dirty()
        return "break"

    def _on_mouse_wheel_activity(self, _event: tk.Event[tk.Misc]) -> None:
        if self.mode == READ_MODE and self.novel is not None:
            # The class binding scrolls after this widget binding completes.
            self.root.after_idle(self._mark_progress_dirty)

    def _scrollbar_command(self, *arguments: str) -> None:
        self.text.yview(*arguments)
        self._mark_progress_dirty()

    def _mark_progress_dirty(self) -> None:
        if self._suspend_progress_tracking or self.novel is None:
            return
        self._progress_dirty = True
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = self.root.after(
            self.settings.progress_save_delay_ms, self._save_debounced_progress
        )

    def _save_debounced_progress(self) -> None:
        self._save_after_id = None
        if self._progress_dirty:
            self.save_current_progress()

    def _top_char_position(self) -> int:
        if self.novel is None:
            return 0
        top_index = self.text.index("@0,0")
        count = self.text.count("1.0", top_index, "chars")
        position = 0 if not count else int(count[0])
        return min(max(0, position), len(self.novel.text))

    def _chapter_for_char(self, char_position: int) -> int:
        if not self._chapter_starts:
            return 0
        return max(0, bisect_right(self._chapter_starts, char_position) - 1)

    def save_current_progress(self) -> None:
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
            self._save_after_id = None
        if self.novel is None or self._pending_char_position is not None:
            return
        char_position = self._top_char_position()
        save_progress(
            PROGRESS_FILE,
            ReadingProgress(
                file_path=str(self.novel.path.resolve()),
                chapter_index=self._chapter_for_char(char_position),
                char_position=char_position,
            ),
        )
        self._progress_dirty = False

    def restore_last_progress(self) -> None:
        saved = load_progress(PROGRESS_FILE)
        if saved is None or not Path(saved.file_path).is_file():
            return
        novel = self._parse_path(Path(saved.file_path))
        if novel is None:
            return
        self._install_novel(novel, saved.char_position)
        if self._pointer_is_inside():
            self.show_read_mode()
        else:
            self.show_work_mode()

    def show_read_mode(self) -> None:
        self._cancel_read_delay()
        self.mode = READ_MODE
        self.work_frame.pack_forget()
        self.toolbar.pack(fill="x", padx=self.settings.padding_x, pady=(12, 0))
        self.read_frame.pack(fill="both", expand=True)
        self.root.update_idletasks()
        self._jump_to_pending_position()
        self.text.focus_set()

    def show_work_mode(self) -> None:
        self.save_current_progress()
        self._cancel_read_delay()
        self.mode = WORK_MODE
        self.read_frame.pack_forget()
        if self.novel is not None:
            self.toolbar.pack_forget()
        self.work_frame.pack(fill="both", expand=True)

    def _boss_key(self, _event: tk.Event[tk.Misc]) -> str:
        try:
            if self.mode == READ_MODE:
                self.show_work_mode()
            elif self.novel is not None and self._pointer_is_inside():
                self.save_current_progress()
                self.show_read_mode()
        except tk.TclError:
            self.show_work_mode()
        return "break"

    def _cancel_read_delay(self) -> None:
        if self._read_after_id is not None:
            self.root.after_cancel(self._read_after_id)
            self._read_after_id = None

    def _pointer_is_inside(self) -> bool:
        x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
        left, top = self.root.winfo_rootx(), self.root.winfo_rooty()
        return left <= x < left + self.root.winfo_width() and top <= y < top + self.root.winfo_height()

    def _poll_pointer(self) -> None:
        try:
            inside = self._pointer_is_inside()
            if inside != self._pointer_inside:
                self._pointer_inside = inside
                if inside:
                    self._schedule_read_mode()
                else:
                    self.show_work_mode()
            self.root.after(120, self._poll_pointer)
        except tk.TclError:
            return

    def _schedule_read_mode(self) -> None:
        self._cancel_read_delay()
        self._read_after_id = self.root.after(self.settings.read_mode_delay_ms, self._read_if_inside)

    def _read_if_inside(self) -> None:
        self._read_after_id = None
        if self._pointer_inside and self.novel is not None:
            self.show_read_mode()

    def close(self) -> None:
        self.save_current_progress()
        self.root.destroy()
