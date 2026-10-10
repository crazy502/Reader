"""Tkinter UI for continuous novel reading and work-mode switching."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from .core.bookshelf import (
    BookFormatMismatchError,
    BookshelfError,
    BookshelfState,
    DuplicateBookPathError,
    books_by_recent_activity,
    load_bookshelf,
    migrate_legacy_progress,
    save_bookshelf,
)
from .core.config import (
    BOOKSHELF_FILE,
    DEFAULT_SETTINGS,
    PROGRESS_FILE,
    WORK_NOTE_FILE,
    ReaderSettings,
    normalize_reading_theme,
)
from .core.novel_parser import Novel, NovelLoadError
from .core.progress import (
    load_progress,
    load_reading_theme,
    save_reading_theme,
)
from .core.work_note import load_work_note, save_work_note as persist_work_note
from .loaders import load_novel
from .ui.bookshelf import BookshelfPage
from .ui.chapter_navigation import ChapterDirectory, chapter_index_for_position
from .ui.reader_view import ReaderView
from .ui.work_view import WorkView
from .i18n import tr


READ_MODE = "read"
WORK_MODE = "work"
BOOK_PAGE = "book"
BOOKSHELF_PAGE = "bookshelf"
DIALOG_HOVER_GRACE_MS = 500


class ReaderApp:
    """Display one continuous novel and persist the top visible character."""

    def __init__(self, root: tk.Tk, settings: ReaderSettings = DEFAULT_SETTINGS) -> None:
        self.root = root
        self.settings = settings
        self.reading_theme = load_reading_theme(PROGRESS_FILE)
        self.bookshelf: BookshelfState = load_bookshelf(BOOKSHELF_FILE)
        if migrate_legacy_progress(self.bookshelf, load_progress(PROGRESS_FILE)):
            save_bookshelf(BOOKSHELF_FILE, self.bookshelf)
        self.novel: Novel | None = None
        self.mode = WORK_MODE
        self.read_page = BOOK_PAGE
        self.hover_reading_enabled = False
        self._read_after_id: str | None = None
        self._leave_after_id: str | None = None
        self._dialog_hover_after_id: str | None = None
        self._save_after_id: str | None = None
        self._work_note_save_after_id: str | None = None
        self._pointer_inside: bool | None = None
        self._suspend_progress_tracking = False
        self._progress_dirty = False
        self._work_note_dirty = False
        self._chapter_starts: tuple[int, ...] = ()
        self._current_chapter_index = -1
        self._chapter_directory: ChapterDirectory | None = None
        self._pending_char_position: int | None = None
        self._dialog_depth = 0
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
        self.read_container = tk.Frame(
            self.container,
            background=self.settings.background_color,
        )
        self.reader_view = ReaderView(
            self.read_container,
            self.settings,
            self.choose_file,
            self.open_bookshelf,
            self.open_chapter_directory,
            self._scrollbar_command,
            self.reading_theme,
            self.set_reading_theme,
        )
        self.bookshelf_page = BookshelfPage(
            self.read_container,
            self.settings,
            books_by_recent_activity(self.bookshelf),
            self.bookshelf.active_book_id,
            self.choose_file,
            self._continue_from_bookshelf,
            self._rename_bookshelf_book,
            self._relocate_bookshelf_book,
            self._remove_bookshelf_book,
        )
        self.work_view = WorkView(
            self.container,
            self.settings,
            self._on_work_note_changed,
            self.enable_hover_reading,
        )
        note_exists = WORK_NOTE_FILE.is_file()
        note = load_work_note(WORK_NOTE_FILE, tr("work_default_note"))
        self.work_view.set_note(note)
        if not note_exists:
            persist_work_note(WORK_NOTE_FILE, note)

    def _bind_events(self) -> None:
        self.reader_view.bind_reading_events(
            self._scroll_with_key,
            self._on_mouse_wheel_activity,
        )
        self.root.bind("<Up>", lambda event: self._scroll_with_key(event, -1))
        self.root.bind("<Down>", lambda event: self._scroll_with_key(event, 1))
        self.root.bind_all("<Leave>", self._on_root_pointer_leave, add="+")
        self.root.bind_all("<Alt-q>", self._boss_key, add="+")

    def choose_file(self) -> None:
        with self._dialog_guard():
            selected = filedialog.askopenfilename(
                title=tr("open_file"),
                filetypes=[
                    (tr("file_types"), "*.txt *.epub"),
                    (tr("all_files"), "*.*"),
                ],
                parent=self.root,
            )
            if selected:
                self.open_novel(Path(selected))

    def open_novel(self, path: Path) -> bool:
        return self._open_novel(path)

    def _open_novel(self, path: Path, preferred_book_id: str | None = None) -> bool:
        self.save_current_progress()
        novel = self._parse_path(path)
        if novel is None:
            return False
        existing = (
            self.bookshelf.books.get(preferred_book_id)
            if preferred_book_id is not None
            else self.bookshelf.find_by_path(path)
        )
        char_position = existing.char_position if existing is not None else 0
        if existing is None:
            self.bookshelf.add_or_activate(path)
        else:
            self.bookshelf.activate(existing.book_id)
        save_bookshelf(BOOKSHELF_FILE, self.bookshelf)
        self._install_novel(novel, char_position)
        self.read_page = BOOK_PAGE
        self.show_read_mode()
        self.save_current_progress()
        return True

    def _parse_path(self, path: Path) -> Novel | None:
        try:
            novel = load_novel(path)
            if not any(chapter.content.strip() for chapter in novel.chapters):
                with self._dialog_guard():
                    messagebox.showwarning(
                        tr("empty_file_title"), tr("empty_file"), parent=self.root
                    )
                return None
            return novel
        except (OSError, NovelLoadError, UnicodeError):
            with self._dialog_guard():
                messagebox.showerror(
                    tr("load_error_title"), tr("load_error"), parent=self.root
                )
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
        if (
            self.read_page != BOOK_PAGE
            or self.novel is None
            or not self.novel.chapters
        ):
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
        if (
            self.mode != READ_MODE
            or self.read_page != BOOK_PAGE
            or self.novel is None
        ):
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

    def open_bookshelf(self) -> None:
        if self.mode != READ_MODE:
            return
        self._close_chapter_directory()
        if self.read_page == BOOK_PAGE:
            self.save_current_progress()
        self._refresh_bookshelf()
        self._set_read_page(BOOKSHELF_PAGE)

    def _set_read_page(self, page: str) -> None:
        if page not in {BOOK_PAGE, BOOKSHELF_PAGE}:
            raise ValueError(f"unknown read page: {page}")
        self.read_page = page
        if self.mode == READ_MODE:
            self._show_current_read_page()

    def _show_current_read_page(self) -> None:
        if self.read_page == BOOKSHELF_PAGE:
            self.reader_view.hide_body()
            self.reader_view.hide_toolbar()
            self.bookshelf_page.show()
            self.bookshelf_page.focus()
            return
        self.bookshelf_page.hide()
        self.reader_view.show()
        self.root.update_idletasks()
        self._jump_to_pending_position()
        self.reader_view.focus()

    def _refresh_bookshelf(self) -> None:
        self.bookshelf_page.refresh(
            books_by_recent_activity(self.bookshelf),
            self.bookshelf.active_book_id,
        )

    def _continue_from_bookshelf(self, book_id: str) -> None:
        book = self.bookshelf.books.get(book_id)
        if book is None:
            return
        path = Path(book.file_path)
        if not path.is_file():
            with self._dialog_guard():
                messagebox.showwarning(
                    tr("bookshelf_missing_title"),
                    tr("bookshelf_missing_message"),
                    parent=self.root,
                )
            return
        if (
            book_id == self.bookshelf.active_book_id
            and self.novel is not None
            and Path(self.novel.path).resolve(strict=False)
            == path.resolve(strict=False)
        ):
            self._set_read_page(BOOK_PAGE)
            return
        self._open_novel(path, preferred_book_id=book_id)

    def _rename_bookshelf_book(self, book_id: str) -> None:
        book = self.bookshelf.books.get(book_id)
        if book is None:
            return
        with self._dialog_guard():
            title = simpledialog.askstring(
                tr("bookshelf_rename_title"),
                tr("bookshelf_rename_prompt"),
                initialvalue=book.display_title,
                parent=self.root,
            )
        if title is None or not title.strip():
            return
        self.bookshelf.rename(book_id, title)
        save_bookshelf(BOOKSHELF_FILE, self.bookshelf)
        self._refresh_bookshelf()

    def _relocate_bookshelf_book(self, book_id: str) -> None:
        book = self.bookshelf.books.get(book_id)
        if book is None:
            return
        pattern = f"*.{book.file_format}"
        with self._dialog_guard():
            selected = filedialog.askopenfilename(
                title=tr("bookshelf_relocate_title"),
                filetypes=[
                    (book.file_format.upper(), pattern),
                    (tr("all_files"), "*.*"),
                ],
                parent=self.root,
            )
        if not selected:
            return
        try:
            self.bookshelf.relocate(book_id, Path(selected))
        except DuplicateBookPathError:
            with self._dialog_guard():
                messagebox.showwarning(
                    tr("bookshelf_relocate_title"),
                    tr("bookshelf_relocate_duplicate"),
                    parent=self.root,
                )
            return
        except (BookFormatMismatchError, BookshelfError):
            with self._dialog_guard():
                messagebox.showwarning(
                    tr("bookshelf_relocate_title"),
                    tr("bookshelf_relocate_format"),
                    parent=self.root,
                )
            return
        save_bookshelf(BOOKSHELF_FILE, self.bookshelf)
        self._refresh_bookshelf()

    def _remove_bookshelf_book(self, book_id: str) -> None:
        book = self.bookshelf.books.get(book_id)
        if book is None:
            return
        with self._dialog_guard():
            confirmed = messagebox.askyesno(
                tr("bookshelf_remove_title"),
                tr("bookshelf_remove_confirm", title=book.display_title),
                parent=self.root,
            )
        if not confirmed:
            return
        removed_active_book = self.bookshelf.active_book_id == book_id
        if removed_active_book:
            self.save_current_progress()
        self.bookshelf.remove(book_id)
        save_bookshelf(BOOKSHELF_FILE, self.bookshelf)
        self._refresh_bookshelf()
        if removed_active_book and self.novel is not None:
            self._set_read_page(BOOK_PAGE)

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

    def _scroll_with_key(self, _event: tk.Event[tk.Misc], direction: int) -> str | None:
        if (
            self.mode == READ_MODE
            and self.read_page == BOOK_PAGE
            and self.novel is not None
        ):
            self.reader_view.scroll_lines(direction * self.settings.key_scroll_lines)
            self._mark_progress_dirty()
            return "break"
        return None

    def _on_mouse_wheel_activity(self, _event: tk.Event[tk.Misc]) -> None:
        if (
            self.mode == READ_MODE
            and self.read_page == BOOK_PAGE
            and self.novel is not None
        ):
            # The class binding scrolls after this widget binding completes.
            self.root.after_idle(self._mark_progress_dirty)

    def _scrollbar_command(self, *arguments: str) -> None:
        if self.mode != READ_MODE or self.read_page != BOOK_PAGE:
            return
        self.reader_view.scroll(*arguments)
        self._mark_progress_dirty()

    def set_reading_theme(self, theme_name: str) -> None:
        """Apply and persist one global ReaderView color theme."""
        self.reading_theme = normalize_reading_theme(theme_name)
        self.reader_view.apply_reading_theme(self.reading_theme)
        save_reading_theme(PROGRESS_FILE, self.reading_theme)

    def _mark_progress_dirty(self) -> None:
        if (
            self._suspend_progress_tracking
            or self.read_page != BOOK_PAGE
            or self.novel is None
        ):
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
        return chapter_index_for_position(self._chapter_starts, char_position)

    def save_current_progress(self) -> None:
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
            self._save_after_id = None
        active_book_id = self.bookshelf.active_book_id
        if (
            self.novel is None
            or self.read_page != BOOK_PAGE
            or self._pending_char_position is not None
            or active_book_id is None
        ):
            return
        char_position = self._top_char_position()
        chapter_index = self._chapter_for_char(char_position)
        chapter_title = (
            self.novel.chapters[chapter_index].title
            if self.novel.chapters
            else ""
        )
        updated = self.bookshelf.update_progress(
            active_book_id,
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            char_position=char_position,
            text_length=len(self.novel.text),
        )
        if updated is not None and save_bookshelf(BOOKSHELF_FILE, self.bookshelf):
            self._progress_dirty = False

    def _on_work_note_changed(self) -> None:
        self._work_note_dirty = True
        if self._work_note_save_after_id is not None:
            self.root.after_cancel(self._work_note_save_after_id)
        self._work_note_save_after_id = self.root.after(
            self.settings.work_note_save_delay_ms,
            self._save_debounced_work_note,
        )

    def _save_debounced_work_note(self) -> None:
        self._work_note_save_after_id = None
        if self._work_note_dirty:
            self.save_work_note()

    def save_work_note(self) -> None:
        if self._work_note_save_after_id is not None:
            self.root.after_cancel(self._work_note_save_after_id)
            self._work_note_save_after_id = None
        if persist_work_note(WORK_NOTE_FILE, self.work_view.get_note()):
            self._work_note_dirty = False
        else:
            self._work_note_dirty = True

    def enable_hover_reading(self) -> None:
        self.save_work_note()
        self.hover_reading_enabled = True
        inside = self._pointer_is_inside()
        self._pointer_inside = inside
        if inside:
            self.show_read_mode()
        else:
            self.show_work_mode()

    def restore_last_progress(self) -> None:
        active_book_id = self.bookshelf.active_book_id
        if active_book_id is None:
            return
        saved = self.bookshelf.books.get(active_book_id)
        if saved is None or not Path(saved.file_path).is_file():
            return
        novel = self._parse_path(Path(saved.file_path))
        if novel is None:
            return
        restored_position = min(max(0, saved.char_position), len(novel.text))
        self._install_novel(novel, restored_position)
        chapter_index = self._chapter_for_char(restored_position)
        chapter_title = (
            novel.chapters[chapter_index].title if novel.chapters else ""
        )
        self.bookshelf.update_progress(
            active_book_id,
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            char_position=restored_position,
            text_length=len(novel.text),
        )
        save_bookshelf(BOOKSHELF_FILE, self.bookshelf)
        if self.hover_reading_enabled and self._pointer_is_inside():
            self.show_read_mode()
        else:
            self.show_work_mode()

    def show_read_mode(self) -> None:
        self._cancel_read_delay()
        self.mode = READ_MODE
        self.work_view.hide()
        self.read_container.pack(fill="both", expand=True)
        self._show_current_read_page()

    def show_work_mode(self) -> None:
        self._close_chapter_directory()
        self.save_current_progress()
        self._cancel_read_delay()
        self.mode = WORK_MODE
        self.read_container.pack_forget()
        self.work_view.show()
        if not self.hover_reading_enabled:
            self.work_view.focus()

    def _boss_key(self, _event: tk.Event[tk.Misc]) -> str:
        try:
            self.hover_reading_enabled = False
            self.save_work_note()
            self.show_work_mode()
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
        inside_chapter_directory = (
            self._chapter_directory is not None
            and self._chapter_directory.contains_screen_point(x, y)
        )
        return inside_chapter_directory

    def _poll_pointer(self) -> None:
        try:
            if self._dialog_depth or self._dialog_hover_after_id is not None:
                self.root.after(120, self._poll_pointer)
                return
            inside = self._pointer_is_inside()
            changed = inside != self._pointer_inside
            self._pointer_inside = inside
            if self.hover_reading_enabled and changed:
                if inside:
                    self._schedule_read_mode()
                else:
                    self.show_work_mode()
            elif not self.hover_reading_enabled:
                self._cancel_read_delay()
            self.root.after(120, self._poll_pointer)
        except tk.TclError:
            return

    def _on_root_pointer_leave(self, _event: tk.Event[tk.Misc]) -> None:
        """Switch to work mode promptly when the pointer truly leaves the app."""
        if (
            not self.hover_reading_enabled
            or self._dialog_depth
            or self._dialog_hover_after_id is not None
        ):
            return
        if self._leave_after_id is None:
            self._leave_after_id = self.root.after_idle(self._work_if_outside)

    def _work_if_outside(self) -> None:
        self._leave_after_id = None
        if not self.hover_reading_enabled or self._dialog_depth:
            return
        inside = self._pointer_is_inside()
        if not inside:
            self._pointer_inside = False
            self._cancel_read_delay()
            self.show_work_mode()

    def _schedule_read_mode(self) -> None:
        self._cancel_read_delay()
        if not self.hover_reading_enabled:
            return
        self._read_after_id = self.root.after(self.settings.read_mode_delay_ms, self._read_if_inside)

    def _read_if_inside(self) -> None:
        self._read_after_id = None
        if self.hover_reading_enabled and self._pointer_inside:
            self.show_read_mode()

    @contextmanager
    def _dialog_guard(self) -> Iterator[None]:
        """Pause hover mode changes while a native modal dialog is active."""
        if self._dialog_depth == 0:
            self._cancel_dialog_hover_grace()
        self._dialog_depth += 1
        self._cancel_read_delay()
        try:
            yield
        finally:
            self._dialog_depth = max(0, self._dialog_depth - 1)
            if self._dialog_depth == 0:
                try:
                    # Treat the pointer position left by the native dialog as a
                    # baseline, not as a new hover boundary transition.
                    self._pointer_inside = self._pointer_is_inside()
                except tk.TclError:
                    self._pointer_inside = None
                if self.hover_reading_enabled:
                    self._dialog_hover_after_id = self.root.after(
                        DIALOG_HOVER_GRACE_MS,
                        self._finish_dialog_hover_grace,
                    )

    def _cancel_dialog_hover_grace(self) -> None:
        if self._dialog_hover_after_id is not None:
            self.root.after_cancel(self._dialog_hover_after_id)
            self._dialog_hover_after_id = None

    def _finish_dialog_hover_grace(self) -> None:
        self._dialog_hover_after_id = None
        if self._dialog_depth or not self.hover_reading_enabled:
            return
        inside = self._pointer_is_inside()
        self._pointer_inside = inside
        if not inside:
            self._cancel_read_delay()
            self.show_work_mode()

    def close(self) -> None:
        self._close_chapter_directory()
        self.save_work_note()
        self.save_current_progress()
        self._cancel_dialog_hover_grace()
        self.root.unbind_all("<Leave>")
        self.root.destroy()
