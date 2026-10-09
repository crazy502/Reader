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
    BookshelfWindow,
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


def _window(
    root: tk.Tk,
    books: list[BookRecord],
    callbacks: dict[str, list[str]],
) -> BookshelfWindow:
    window = BookshelfWindow(
        root,
        DEFAULT_SETTINGS,
        books,
        books[0].book_id if books else None,
        lambda book_id: callbacks["continue"].append(book_id),
        lambda book_id: callbacks["rename"].append(book_id),
        lambda book_id: callbacks["relocate"].append(book_id),
        lambda book_id: callbacks["remove"].append(book_id),
        lambda: None,
    )
    root.update()
    return window


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
    window = _window(tk_root, ordered, callbacks)

    assert window._ordered_book_ids == [recent.book_id, older.book_id]
    assert window._cards[recent.book_id].title_label.cget("text") == "新书"
    window._cards[recent.book_id].cover.event_generate("<Button-1>", x=20, y=20)
    tk_root.update()

    assert callbacks["continue"] == [recent.book_id]
    window.close()


def test_missing_card_prompts_for_relocation_instead_of_reading(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    missing = _record(tmp_path / "Missing.epub", "missing-book")
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _window(tk_root, [missing], callbacks)
    card = window._cards[missing.book_id]

    assert card.is_missing
    assert card.missing_label is not None
    card.cover.event_generate("<Button-1>", x=20, y=20)
    tk_root.update()

    assert callbacks["continue"] == []
    assert window.missing_prompt.grid_info()
    window.relocate_button.invoke()
    assert callbacks["relocate"] == [missing.book_id]
    window.close()


def test_right_click_menu_routes_management_actions_to_the_same_book(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    available = tmp_path / "Managed.txt"
    available.write_text("body", encoding="utf-8")
    book = _record(available, "managed-book")
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _window(tk_root, [book], callbacks)
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
    window.close()


def test_refresh_updates_renamed_relocated_and_removed_cards(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    missing = _record(tmp_path / "Missing.txt", "refresh-book", title="原书名")
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _window(tk_root, [missing], callbacks)
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
    window.close()


def test_scroll_and_resize_reflow_keep_cards_in_a_valid_grid(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    available = tmp_path / "Book.txt"
    available.write_text("body", encoding="utf-8")
    books = [_record(available, f"book-{index}", title=f"第{index}本书") for index in range(30)]
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _window(tk_root, books, callbacks)
    _run_tk_for(tk_root, 100)

    before = window.canvas.yview()[0]
    window._on_mousewheel(SimpleNamespace(delta=-120))
    tk_root.update()
    assert window.canvas.yview()[0] > before

    window.window.geometry("440x420")
    _run_tk_for(tk_root, 120)
    narrow_columns = window.column_count
    window.window.geometry("760x520")
    _run_tk_for(tk_root, 120)
    wide_columns = window.column_count

    assert narrow_columns < wide_columns
    assert all(
        int(card.frame.grid_info()["column"]) < wide_columns
        for card in window._cards.values()
    )
    window.close()


def test_default_760_by_620_layout_uses_book_sized_non_overlapping_cards(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    available = tmp_path / "Visual.txt"
    available.write_text("body", encoding="utf-8")
    books = [_record(available, f"visual-{index}") for index in range(12)]
    callbacks = {key: [] for key in ("continue", "rename", "relocate", "remove")}
    window = _window(tk_root, books, callbacks)
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
    window.close()


def test_alt_q_closes_bookshelf_and_bookshelf_counts_as_hover_area(
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
    shelf = app._bookshelf_window
    assert shelf is not None

    center_x = shelf.window.winfo_rootx() + shelf.window.winfo_width() // 2
    center_y = shelf.window.winfo_rooty() + shelf.window.winfo_height() // 2
    monkeypatch.setattr(app_root, "winfo_pointerx", lambda: center_x)
    monkeypatch.setattr(app_root, "winfo_pointery", lambda: center_y)
    assert app._pointer_is_inside()

    app.hover_reading_enabled = True
    app._boss_key(None)
    tk_root.update()
    assert app.mode == app_module.WORK_MODE
    assert not app.hover_reading_enabled
    assert app._bookshelf_window is None
    app.close()
