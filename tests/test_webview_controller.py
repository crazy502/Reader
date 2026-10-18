from __future__ import annotations

from pathlib import Path
import threading

import main as root_entry
from reader.webview import app as webview_app
from reader.webview.app import create_app_window
from reader.webview.controller import WebViewApi, WebViewController
from reader.webview.storage import NotebookStorage


class _CloseWindowStub:
    def __init__(self, snapshot: dict[str, object]) -> None:
        self.snapshot = snapshot
        self.destroyed = threading.Event()

    def evaluate_js(self, _script: str) -> dict[str, object]:
        return self.snapshot

    def destroy(self) -> None:
        self.destroyed.set()


class _EventHook:
    def __init__(self) -> None:
        self.handlers: list[object] = []

    def __iadd__(self, handler: object) -> _EventHook:
        self.handlers.append(handler)
        return self


class _WindowStub:
    def __init__(self) -> None:
        self.events = type(
            "Events",
            (),
            {"closing": _EventHook(), "closed": _EventHook()},
        )()


def _write_book(path: Path, label: str) -> Path:
    path.write_text(
        f"第一章 {label}\n\n这是第一章正文。\n\n第二章 继续\n\n这是第二章正文。",
        encoding="utf-8",
    )
    return path


def test_root_entry_and_window_use_formal_webview_app(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, object] = {}
    window = _WindowStub()

    def create_window(title: str, **options: object) -> _WindowStub:
        captured.update({"title": title, **options})
        return window

    monkeypatch.setattr(webview_app.webview, "create_window", create_window)

    controller, created = create_app_window(data_dir=tmp_path / "data")

    assert root_entry.main is webview_app.main
    assert captured["title"] == "Notebook"
    assert str(captured["url"]).endswith("reader\\webview\\web\\index.html")
    assert created is window
    assert controller._storage.data_dir == (tmp_path / "data").resolve()
    assert window.events.closing.handlers == [controller.on_closing]
    assert window.events.closed.handlers == [controller.on_closed]


def test_api_exposes_only_production_endpoints(tmp_path: Path) -> None:
    api = WebViewApi(WebViewController(data_dir=tmp_path / "data"))

    assert hasattr(api, "prepare_book")
    assert hasattr(api, "save_position")
    assert not hasattr(api, "prepare_synthetic_book")
    assert not hasattr(api, "get_process_metrics")


def test_two_books_keep_independent_positions_after_restart(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    controller = WebViewController(data_dir=data_dir)
    first = controller._storage.add_book(_write_book(tmp_path / "a.txt", "甲"))
    second = controller._storage.add_book(_write_book(tmp_path / "b.txt", "乙"))

    for record, position in ((first, 11), (second, 29)):
        controller.prepare_book(record["book_id"])
        controller.commit_book(record["book_id"])
        controller.save_position(record["book_id"], position)

    restored = NotebookStorage(data_dir)
    assert restored.record(first["book_id"]).char_position == 11
    assert restored.record(second["book_id"]).char_position == 29
    assert restored.state.active_book_id == second["book_id"]


def test_close_saves_snapshot_before_window_destruction(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    controller = WebViewController(data_dir=data_dir)
    record = controller._storage.add_book(_write_book(tmp_path / "close.txt", "关闭"))
    controller.prepare_book(record["book_id"])
    controller.commit_book(record["book_id"])
    window = _CloseWindowStub(
        {
            "work_note": "关闭前便笺🙂",
            "reading_theme": "eye_care",
            "book_id": record["book_id"],
            "char_position": 17,
        }
    )
    controller.attach(window)  # type: ignore[arg-type]

    assert controller.on_closing() is False
    assert window.destroyed.wait(2)
    assert controller.on_closing() is None

    restored = NotebookStorage(data_dir)
    assert restored.snapshot()["work_note"] == "关闭前便笺🙂"
    assert restored.reading_theme == "eye_care"
    assert restored.record(record["book_id"]).char_position == 17
