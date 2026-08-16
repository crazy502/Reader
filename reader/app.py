"""Tkinter UI for continuous TXT reading and work-mode switching."""

from __future__ import annotations

from bisect import bisect_right
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from .core.config import DEFAULT_SETTINGS, PROGRESS_FILE, ReaderSettings
from .core.novel_parser import Novel, NovelLoadError, parse_novel
from .core.progress import ReadingProgress, load_progress, save_progress
from .ui.chapter_navigation import ChapterDirectory
from .ui.reader_view import ReaderView
from .ui.work_view import WorkView
from .i18n import tr


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
        self._current_chapter_index = -1
        self._chapter_directory: ChapterDirectory | None = None
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
        self.reader_view = ReaderView(
            self.container,
            self.settings,
            self.choose_file,
            self.open_chapter_directory,
            self._scrollbar_command,
        )
        self.work_view = WorkView(self.container, self.settings)

    def _bind_events(self) -> None:
        self.reader_view.bind_reading_events(
            self._scroll_with_key,
            self._on_mouse_wheel_activity,
        )
        self.root.bind("<Up>", lambda event: self._scroll_with_key(event, -1))
        self.root.bind("<Down>", lambda event: self._scroll_with_key(event, 1))
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
        self._current_chapter_index = -1
        self._suspend_progress_tracking = True
        try:
            self.reader_view.install_novel(novel)
            self._pending_char_position = min(max(0, char_position), len(novel.text))
            self._set_current_chapter(self._chapter_for_char(self._pending_char_position))
            if self.reader_view.is_mapped():
                self._jump_to_pending_position()
        finally:
            self._suspend_progress_tracking = False
        self._progress_dirty = False

    def _jump_to_char(self, char_position: int) -> None:
        if self.novel is None:
            return
        position = min(max(0, char_position), len(self.novel.text))
        self.reader_view.jump_to_char(position)
        self.root.update_idletasks()
        self._update_current_chapter()

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

    def open_chapter_directory(self) -> None:
        if self.mode != READ_MODE or self.novel is None:
            return
        if self._chapter_directory is not None:
            self._chapter_directory.focus()
            return
        self._update_current_chapter()
        self._chapter_directory = ChapterDirectory(
            self.root,
            self.novel.chapters,
            self._current_chapter_index,
            self.jump_to_chapter,
            self._chapter_directory_closed,
        )

    def _chapter_directory_closed(self) -> None:
        self._chapter_directory = None

    def _close_chapter_directory(self) -> None:
        if self._chapter_directory is None:
            return
        directory = self._chapter_directory
        self._chapter_directory = None
        directory.close()

    def _set_current_chapter(self, chapter_index: int) -> None:
        if self.novel is None or not self.novel.chapters:
            return
        index = min(max(0, chapter_index), len(self.novel.chapters) - 1)
        if index == self._current_chapter_index:
            return
        self._current_chapter_index = index
        self.reader_view.set_chapter_title(self.novel.chapters[index].title)

    def _update_current_chapter(self) -> None:
        if self.novel is None:
            return
        char_position = (
            self._pending_char_position
            if self._pending_char_position is not None
            else self._top_char_position()
        )
        self._set_current_chapter(self._chapter_for_char(char_position))

    def _scroll_with_key(self, _event: tk.Event[tk.Misc], direction: int) -> str:
        if self.mode == READ_MODE and self.novel is not None:
            self.reader_view.scroll_lines(direction * self.settings.key_scroll_lines)
            self._mark_progress_dirty()
        return "break"

    def _on_mouse_wheel_activity(self, _event: tk.Event[tk.Misc]) -> None:
        if self.mode == READ_MODE and self.novel is not None:
            # The class binding scrolls after this widget binding completes.
            self.root.after_idle(self._mark_progress_dirty)

    def _scrollbar_command(self, *arguments: str) -> None:
        self.reader_view.scroll(*arguments)
        self._mark_progress_dirty()

    def _mark_progress_dirty(self) -> None:
        if self._suspend_progress_tracking or self.novel is None:
            return
        self._update_current_chapter()
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
        position = self.reader_view.top_char_position()
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
        self.work_view.hide()
        self.reader_view.show()
        self.root.update_idletasks()
        self._jump_to_pending_position()
        self.reader_view.focus()

    def show_work_mode(self) -> None:
        self._close_chapter_directory()
        self.save_current_progress()
        self._cancel_read_delay()
        self.mode = WORK_MODE
        self.reader_view.hide_body()
        if self.novel is not None:
            self.reader_view.hide_toolbar()
        self.work_view.show()

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
        inside_reader = (
            left <= x < left + self.root.winfo_width()
            and top <= y < top + self.root.winfo_height()
        )
        if inside_reader:
            return True
        return (
            self._chapter_directory is not None
            and self._chapter_directory.contains_screen_point(x, y)
        )

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
        self._close_chapter_directory()
        self.save_current_progress()
        self.root.destroy()
