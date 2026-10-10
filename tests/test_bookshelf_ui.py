from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk

import pytest

from reader.core.bookshelf import BookRecord, BookshelfState, books_by_recent_activity
from reader.core.config import DEFAULT_SETTINGS
from reader.platform.dpi_awareness import configure as configure_dpi_awareness
from reader.platform.tk_runtime import configure as configure_tk_runtime
from reader.ui.bookshelf import (
    COVER_COLORS,
    MAX_COVER_TITLE_LENGTH,
    BookshelfPage,
    column_count_for_width,
    cover_color_for_book,
    display_book_progress,
    display_cover_title,
)


configure_dpi_awareness()
configure_tk_runtime()


@pytest.fixture(scope="module")
def tk_root() -> Iterator[tk.Tk]:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk is unavailable: {error}")
    root.geometry("760x620+5000+5000")
    root.update_idletasks()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _record(
    path: Path,
    book_id: str,
    *,
    title: str = "神明游戏",
    chapter: str = "第二十一章",
    position: int = 630,
    length: int = 1000,
    opened_at: str = "2026-09-13T08:00:00Z",
) -> BookRecord:
    return BookRecord(
        book_id=book_id,
        file_path=str(path),
        display_title=title,
        file_format=path.suffix.lstrip(".") or "txt",
        chapter_index=20,
        chapter_title=chapter,
        char_position=position,
        text_length=length,
        last_opened_at=opened_at,
    )


def _page(
    root: tk.Tk,
    books: list[BookRecord],
    callbacks: dict[str, list[str]],
) -> BookshelfPage:
    page = BookshelfPage(
        root,
        DEFAULT_SETTINGS,
        books,
        books[0].book_id if books else None,
        lambda: callbacks.setdefault("add", []).append("add"),
        lambda book_id: callbacks["continue"].append(book_id),
        lambda book_id: callbacks["rename"].append(book_id),
        lambda book_id: callbacks["relocate"].append(book_id),
        lambda book_id: callbacks["remove"].append(book_id),
    )
    page.show()
    root.update()
    return page


def _run_tk_for(root: tk.Tk, milliseconds: int) -> None:
    root.after(milliseconds, root.quit)
    root.mainloop()


def test_card_presentation_is_stable_compact_and_accurate(tmp_path: Path) -> None:
    book = _record(tmp_path / "Game.txt", "book-stable-color")
    long_title = "这是一本书名非常非常非常长并且不应该撑坏书架布局的中文小说"

    assert cover_color_for_book(book.book_id) == cover_color_for_book(book.book_id)
    assert cover_color_for_book(book.book_id) in COVER_COLORS
    assert display_book_progress(book) == "63% · 第二十一章"
    assert display_cover_title("  神明   游戏  ") == "神明 游戏"
    assert len(display_cover_title(long_title)) == MAX_COVER_TITLE_LENGTH
    assert display_cover_title(long_title).endswith("…")


def test_embedded_bookshelf_add_button_routes_to_file_picker(
    tk_root: tk.Tk,
) -> None:
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    page = _page(tk_root, [], callbacks)

    page.add_button.invoke()

    assert callbacks["add"] == ["add"]
    page.destroy()


def test_column_count_changes_without_allowing_overlap() -> None:
    assert column_count_for_width(440) == 2
    assert column_count_for_width(720) == 4
    assert column_count_for_width(900) == 5
    assert column_count_for_width(1) == 1


def test_recent_order_and_single_click_use_the_correct_book_id(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    available = tmp_path / "Recent.txt"
    available.write_text("body", encoding="utf-8")
    older = _record(
        available,
        "older-book",
        title="旧书",
        opened_at="2026-09-12T08:00:00Z",
    )
    recent = _record(
        available,
        "recent-book",
        title="新书",
        opened_at="2026-09-13T08:00:00Z",
    )
    ordered = books_by_recent_activity(
        BookshelfState(books={older.book_id: older, recent.book_id: recent})
    )
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _page(tk_root, ordered, callbacks)

    assert window._ordered_book_ids == [recent.book_id, older.book_id]
    assert window._cards[recent.book_id].title_label.cget("text") == "新书"
    window._cards[recent.book_id].cover.event_generate("<Button-1>", x=20, y=20)
    tk_root.update()

    assert callbacks["continue"] == [recent.book_id]
    window.destroy()


def test_missing_card_prompts_for_relocation_instead_of_reading(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    missing = _record(tmp_path / "Missing.epub", "missing-book")
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _page(tk_root, [missing], callbacks)
    card = window._cards[missing.book_id]

    assert card.is_missing
    assert card.missing_label is not None
    card.cover.event_generate("<Button-1>", x=20, y=20)
    tk_root.update()

    assert callbacks["continue"] == []
    assert window.missing_prompt.grid_info()
    window.relocate_button.invoke()
    assert callbacks["relocate"] == [missing.book_id]
    window.destroy()


def test_right_click_menu_routes_management_actions_to_the_same_book(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    available = tmp_path / "Managed.txt"
    available.write_text("body", encoding="utf-8")
    book = _record(available, "managed-book")
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _page(tk_root, [book], callbacks)
    monkeypatch.setattr(tk.Menu, "tk_popup", lambda *_arguments: None)

    window._cards[book.book_id].cover.event_generate("<Button-3>", x=20, y=20)
    tk_root.update()
    menu = window._context_menu
    assert menu is not None

    menu.invoke(0)
    menu.invoke(1)
    menu.invoke(3)
    assert callbacks["rename"] == [book.book_id]
    assert callbacks["relocate"] == [book.book_id]
    assert callbacks["remove"] == [book.book_id]
    window.destroy()


def test_refresh_updates_renamed_relocated_and_removed_cards(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    missing = _record(tmp_path / "Missing.txt", "refresh-book", title="原书名")
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _page(tk_root, [missing], callbacks)
    assert window._cards[missing.book_id].is_missing

    relocated_path = tmp_path / "Relocated.txt"
    relocated_path.write_text("body", encoding="utf-8")
    updated = replace(
        missing,
        file_path=str(relocated_path),
        display_title="修改后的书名",
    )
    window.refresh([updated], updated.book_id)
    tk_root.update()

    assert window._cards[updated.book_id].title_label.cget("text") == "修改后的书名"
    assert not window._cards[updated.book_id].is_missing

    window.refresh([], None)
    tk_root.update()
    assert window._cards == {}
    assert window.empty_label.grid_info()
    window.destroy()


def test_scroll_and_resize_reflow_keep_cards_in_a_valid_grid(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    available = tmp_path / "Book.txt"
    available.write_text("body", encoding="utf-8")
    books = [_record(available, f"book-{index}", title=f"第{index}本书") for index in range(30)]
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _page(tk_root, books, callbacks)
    _run_tk_for(tk_root, 100)

    before = window.canvas.yview()[0]
    window._on_mousewheel(SimpleNamespace(delta=-120))
    tk_root.update()
    assert window.canvas.yview()[0] > before

    tk_root.geometry("440x420+5000+5000")
    _run_tk_for(tk_root, 120)
    narrow_columns = window.column_count
    tk_root.geometry("760x520+5000+5000")
    _run_tk_for(tk_root, 120)
    wide_columns = window.column_count

    assert narrow_columns < wide_columns
    assert all(
        int(card.frame.grid_info()["column"]) < wide_columns
        for card in window._cards.values()
    )
    window.destroy()
    tk_root.geometry("760x620+5000+5000")
    tk_root.update_idletasks()


def test_default_760_by_620_layout_uses_book_sized_non_overlapping_cards(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    available = tmp_path / "Visual.txt"
    available.write_text("body", encoding="utf-8")
    books = [_record(available, f"visual-{index}") for index in range(12)]
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _page(tk_root, books, callbacks)
    _run_tk_for(tk_root, 120)

    assert tk_root.winfo_width() == 760
    assert tk_root.winfo_height() == 620
    assert window.column_count == 4
    first_card = window._cards[books[0].book_id]
    assert first_card.cover.winfo_width() == 132
    assert first_card.cover.winfo_height() == 172
    assert first_card.frame.winfo_width() == 132
    assert all(
        int(card.frame.grid_info()["column"]) < window.column_count
        for card in window._cards.values()
    )
    window.destroy()


def test_alt_q_preserves_embedded_bookshelf_page_and_disables_hover(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import reader.app as app_module

    monkeypatch.setattr(app_module, "PROGRESS_FILE", tmp_path / "reader_config.json")
    monkeypatch.setattr(app_module, "BOOKSHELF_FILE", tmp_path / "bookshelf.json")
    monkeypatch.setattr(app_module, "WORK_NOTE_FILE", tmp_path / "work_note.txt")
    app_root = tk.Toplevel(tk_root)
    app = app_module.ReaderApp(app_root)
    app.show_read_mode()
    app.open_bookshelf()
    tk_root.update()
    assert app.read_page == app_module.BOOKSHELF_PAGE
    assert app.bookshelf_page.frame.winfo_ismapped()

    center_x = app_root.winfo_rootx() + app_root.winfo_width() // 2
    center_y = app_root.winfo_rooty() + app_root.winfo_height() // 2
    monkeypatch.setattr(app_root, "winfo_pointerx", lambda: center_x)
    monkeypatch.setattr(app_root, "winfo_pointery", lambda: center_y)
    assert app._pointer_is_inside()

    app.hover_reading_enabled = True
    app._boss_key(None)
    tk_root.update()
    assert app.mode == app_module.WORK_MODE
    assert not app.hover_reading_enabled
    assert app.read_page == app_module.BOOKSHELF_PAGE
    app.close()


def _novel_file(directory: Path, name: str, marker: str) -> Path:
    lines = ["第一章 开始"]
    lines.extend(f"{marker} 第一章正文第{index}行。" for index in range(90))
    lines.append("第二章 继续")
    lines.extend(f"{marker} 第二章正文第{index}行。" for index in range(90))
    path = directory / name
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _reader_app(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[object, object]:
    import reader.app as app_module

    monkeypatch.setattr(app_module, "PROGRESS_FILE", tmp_path / "reader_config.json")
    monkeypatch.setattr(app_module, "BOOKSHELF_FILE", tmp_path / "bookshelf.json")
    monkeypatch.setattr(app_module, "WORK_NOTE_FILE", tmp_path / "work_note.txt")
    app_root = tk.Toplevel(tk_root)
    app_root.geometry("760x620+5000+5000")
    app = app_module.ReaderApp(app_root)
    _run_tk_for(tk_root, 130)
    return app_module, app


def test_empty_bookshelf_is_an_embedded_read_page(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)

    app.show_read_mode()
    app.open_bookshelf()
    tk_root.update()

    assert app.mode == app_module.READ_MODE
    assert app.read_page == app_module.BOOKSHELF_PAGE
    assert app.bookshelf_page.frame.master is app.read_container
    assert app.bookshelf_page.frame.winfo_ismapped()
    assert not app.bookshelf_page._cards
    assert app.bookshelf_page.empty_label.grid_info()
    app.close()


def test_current_book_fast_return_keeps_text_widget_and_position(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)
    path = _novel_file(tmp_path, "A.txt", "A")
    assert app.open_novel(path)
    tk_root.update()
    text_widget = app.reader_view.text
    app.reader_view.jump_to_char(900)
    tk_root.update_idletasks()
    position_before = app.reader_view.top_char_position()
    app._mark_progress_dirty()
    assert app._save_after_id is not None

    app.open_bookshelf()
    assert app._save_after_id is None
    active_book_id = app.bookshelf.active_book_id
    assert active_book_id is not None
    parse_calls: list[Path] = []
    original_parse = app._parse_path

    def tracked_parse(selected: Path):
        parse_calls.append(selected)
        return original_parse(selected)

    monkeypatch.setattr(app, "_parse_path", tracked_parse)
    app._continue_from_bookshelf(active_book_id)
    tk_root.update()

    assert app.read_page == app_module.BOOK_PAGE
    assert app.reader_view.text is text_widget
    assert app.reader_view.top_char_position() == position_before
    assert parse_calls == []
    app.close()


def test_switching_two_books_restores_independent_character_positions(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)
    path_a = _novel_file(tmp_path, "A.txt", "A")
    path_b = _novel_file(tmp_path, "B.txt", "B")
    text_widget = app.reader_view.text

    assert app.open_novel(path_a)
    app.reader_view.jump_to_char(700)
    tk_root.update_idletasks()
    app.open_bookshelf()
    book_a = app.bookshelf.find_by_path(path_a)
    assert book_a is not None
    position_a = app.bookshelf.books[book_a.book_id].char_position

    assert app.open_novel(path_b)
    app.reader_view.jump_to_char(1300)
    tk_root.update_idletasks()
    app.open_bookshelf()
    book_b = app.bookshelf.find_by_path(path_b)
    assert book_b is not None
    position_b = app.bookshelf.books[book_b.book_id].char_position
    assert position_a != position_b

    app._continue_from_bookshelf(book_a.book_id)
    tk_root.update_idletasks()
    assert app.read_page == app_module.BOOK_PAGE
    assert app.reader_view.text is text_widget
    assert app.reader_view.top_char_position() == position_a

    app.open_bookshelf()
    app._continue_from_bookshelf(book_b.book_id)
    tk_root.update_idletasks()
    assert app.reader_view.top_char_position() == position_b
    assert app.bookshelf.books[book_a.book_id].char_position == position_a
    assert app.bookshelf.books[book_b.book_id].char_position == position_b
    app.close()


def test_read_page_survives_work_mode_and_hidden_reader_input_is_blocked(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)
    path = _novel_file(tmp_path, "A.txt", "A")
    assert app.open_novel(path)
    app.open_bookshelf()
    position_before = app.reader_view.top_char_position()

    assert app._scroll_with_key(None, 1) is None
    assert app.reader_view.top_char_position() == position_before
    app.open_chapter_directory()
    assert app._chapter_directory is None

    app.show_work_mode()
    assert app.read_page == app_module.BOOKSHELF_PAGE
    app.show_read_mode()
    tk_root.update()
    assert app.read_page == app_module.BOOKSHELF_PAGE
    assert app.bookshelf_page.frame.winfo_ismapped()

    app._set_read_page(app_module.BOOK_PAGE)
    app.show_work_mode()
    app.show_read_mode()
    tk_root.update()
    assert app.read_page == app_module.BOOK_PAGE
    assert app.reader_view.text.winfo_ismapped()
    app.close()


def test_native_dialog_guard_pauses_hover_transitions(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)
    path = _novel_file(tmp_path, "A.txt", "A")
    assert app.open_novel(path)
    app.open_bookshelf()
    app.hover_reading_enabled = True
    app._pointer_inside = True
    observed_depths: list[int] = []

    def cancelled_file_dialog(**_kwargs: object) -> str:
        observed_depths.append(app._dialog_depth)
        app._poll_pointer()
        assert app.mode == app_module.READ_MODE
        return ""

    monkeypatch.setattr("reader.app.filedialog.askopenfilename", cancelled_file_dialog)
    app.choose_file()
    book_id = app.bookshelf.active_book_id
    assert book_id is not None
    monkeypatch.setattr(
        "reader.app.simpledialog.askstring",
        lambda *_args, **_kwargs: observed_depths.append(app._dialog_depth) or None,
    )
    app._rename_bookshelf_book(book_id)
    app._relocate_bookshelf_book(book_id)

    assert observed_depths == [1, 1, 1]
    assert app._dialog_depth == 0
    assert app.mode == app_module.READ_MODE
    assert app.read_page == app_module.BOOKSHELF_PAGE
    app.close()


def test_adding_book_from_shelf_opens_book_page_without_false_hover_exit(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)
    path = _novel_file(tmp_path, "Added.txt", "新增")
    app.show_read_mode()
    app.open_bookshelf()
    app.hover_reading_enabled = True
    monkeypatch.setattr(app, "_pointer_is_inside", lambda: False)
    monkeypatch.setattr(
        "reader.app.filedialog.askopenfilename",
        lambda **_kwargs: str(path),
    )

    app.choose_file()
    app._poll_pointer()

    assert app.mode == app_module.READ_MODE
    assert app.read_page == app_module.BOOK_PAGE
    assert app.bookshelf.active_book_id is not None
    assert app.bookshelf.find_by_path(path) is not None
    assert app._pointer_inside is False
    assert app.hover_reading_enabled
    app.close()


def test_cancelled_file_picker_preserves_current_read_page(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)
    app.show_read_mode()
    app.open_bookshelf()
    app.hover_reading_enabled = True
    monkeypatch.setattr(app, "_pointer_is_inside", lambda: False)
    monkeypatch.setattr(
        "reader.app.filedialog.askopenfilename",
        lambda **_kwargs: "",
    )

    app.choose_file()
    app._poll_pointer()

    assert app.mode == app_module.READ_MODE
    assert app.read_page == app_module.BOOKSHELF_PAGE
    assert app.hover_reading_enabled
    app.close()


def test_dialog_hover_protection_is_temporary(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)
    app.show_read_mode()
    app.open_bookshelf()
    app.hover_reading_enabled = True
    monkeypatch.setattr(app, "_pointer_is_inside", lambda: False)
    monkeypatch.setattr(
        "reader.app.filedialog.askopenfilename",
        lambda **_kwargs: "",
    )

    app.choose_file()

    assert app.mode == app_module.READ_MODE
    assert app._dialog_hover_after_id is not None
    _run_tk_for(tk_root, app_module.DIALOG_HOVER_GRACE_MS + 60)
    assert app.mode == app_module.WORK_MODE
    assert app.read_page == app_module.BOOKSHELF_PAGE
    assert app._dialog_hover_after_id is None
    app.close()


def test_root_leave_switches_to_work_immediately_and_cancels_enter_delay(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)
    path = _novel_file(tmp_path, "A.txt", "A")
    assert app.open_novel(path)
    app.hover_reading_enabled = True
    app._pointer_inside = True
    app._schedule_read_mode()
    assert app._read_after_id is not None
    monkeypatch.setattr(app, "_pointer_is_inside", lambda: False)

    app.root.event_generate("<Leave>")
    tk_root.update()

    assert app.mode == app_module.WORK_MODE
    assert app._read_after_id is None
    assert app._pointer_inside is False
    app.close()


def test_pointer_enter_still_schedules_configured_restore_delay(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module, app = _reader_app(tk_root, tmp_path, monkeypatch)
    app.show_work_mode()
    app.hover_reading_enabled = True
    app._pointer_inside = False
    scheduled: list[tuple[int, object]] = []

    def record_after(delay: int, callback: object) -> str:
        scheduled.append((delay, callback))
        return f"after-{len(scheduled)}"

    monkeypatch.setattr(app.root, "after", record_after)
    monkeypatch.setattr(app, "_pointer_is_inside", lambda: True)

    app._poll_pointer()

    assert app.mode == app_module.WORK_MODE
    assert any(
        delay == app.settings.read_mode_delay_ms and callback == app._read_if_inside
        for delay, callback in scheduled
    )
    assert app.settings.read_mode_delay_ms == 400
    app.close()
