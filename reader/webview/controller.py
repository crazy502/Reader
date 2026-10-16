"""Window controller and JavaScript bridge for Notebook WebView2."""

from __future__ import annotations

import base64
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

import webview

from .i18n import tr
from .novel_engine import NovelEngineError, NovelLibrary
from .storage import PreviewStorage, PreviewStorageError


APP_TITLE = tr("preview_title")
WINDOW_WIDTH = 760
WINDOW_HEIGHT = 620
WINDOW_MIN_SIZE = (470, 360)
ENTER_DELAY_SECONDS = 0.4
POINTER_POLL_SECONDS = 0.04
class Point(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class Rect(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def point_in_rect(point: Point, rect: Rect) -> bool:
    return rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom


def detect_webview2_runtime() -> dict[str, str | None]:
    roots = [
        Path(os.environ.get("ProgramFiles(x86)", ""))
        / "Microsoft"
        / "EdgeWebView"
        / "Application",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft"
        / "EdgeWebView"
        / "Application",
    ]
    candidates: list[tuple[str, Path]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for executable in root.glob("*/msedgewebview2.exe"):
            candidates.append((executable.parent.name, executable))
    if not candidates:
        return {"version": None, "executable": None}
    runtime_version, executable = sorted(candidates, reverse=True)[0]
    return {"version": runtime_version, "executable": str(executable)}


class NativeWindowProbe:
    """Read the complete native window boundary, not the HTML document boundary."""

    def __init__(self, window: webview.Window) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Native hover probing is only implemented for Windows.")
        self.window = window
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetCursorPos.argtypes = [ctypes.POINTER(Point)]
        self.user32.GetCursorPos.restype = wintypes.BOOL
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(Rect)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
        self.user32.IsIconic.argtypes = [wintypes.HWND]
        self.user32.IsIconic.restype = wintypes.BOOL
        self.user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        self.user32.GetSystemMetrics.restype = ctypes.c_int

    def hwnd(self) -> int:
        native = self.window.native
        if native is None:
            raise RuntimeError("pywebview native window is not ready.")
        return int(native.Handle.ToInt64())

    def snapshot(self) -> dict[str, Any]:
        hwnd = self.hwnd()
        point = Point()
        rect = Rect()
        if not self.user32.GetCursorPos(ctypes.byref(point)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        minimized = bool(self.user32.IsIconic(hwnd))
        return {
            "hwnd": hwnd,
            "cursor": {"x": point.x, "y": point.y},
            "rect": {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
            },
            "inside": False if minimized else point_in_rect(point, rect),
            "minimized": minimized,
        }

    def virtual_screen(self) -> dict[str, int]:
        return {
            "left": self.user32.GetSystemMetrics(76),
            "top": self.user32.GetSystemMetrics(77),
            "width": self.user32.GetSystemMetrics(78),
            "height": self.user32.GetSystemMetrics(79),
        }


class WebViewController:
    def __init__(
        self,
        *,
        preview_mode: bool = False,
        preview_data_dir: Path | None = None,
    ) -> None:
        self.window: webview.Window | None = None
        self.preview_mode = preview_mode
        self.run_error: str | None = None
        self.renderer = "not-started"
        self.runtime = detect_webview2_runtime()
        self.app_mode = "work"
        self.hover_reading_enabled = False
        self._last_inside: bool | None = None
        self._inside_since: float | None = None
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._probe: NativeWindowProbe | None = None
        self._dialog_depth = 0
        self._dialog_guard_until = 0.0
        self._close_save_started = False
        self._allow_close = False
        self._library = NovelLibrary()
        self._preview = PreviewStorage(preview_data_dir) if preview_mode else None
        self._preview_library_ids: dict[str, str] = {}
        self._preview_library_paths: dict[str, str] = {}

    def attach(self, window: webview.Window) -> None:
        self.window = window

    def run(self) -> None:
        if self.initialize() is not None:
            self._monitor_pointer()

    def initialize(self) -> dict[str, Any] | None:
        assert self.window is not None
        if not self.window.events.loaded.wait(20):
            self._fail("HTML 页面在 20 秒内未完成加载。")
            return None

        self.renderer = str(webview.renderer or "unknown")
        if self.renderer != "edgechromium":
            self._fail(f"实际 GUI 后端为 {self.renderer}，拒绝将其视为 WebView2 验证。")
            return None

        try:
            self._probe = NativeWindowProbe(self.window)
            native_snapshot = self._probe.snapshot()
            self._notify_frontend(
                {
                    "ok": True,
                    "message": (
                        f"Python 主动通知 · {self.renderer} · "
                        f"WebView2 {self.runtime['version'] or '版本未知'}"
                    ),
                    "native_window": native_snapshot,
                }
            )
            self._set_mode("work", "startup")
            if self.preview_mode:
                self._evaluate(
                    "window.notebookPreview.bootstrap"
                    f"({json.dumps(self.preview_snapshot(), ensure_ascii=False)})"
                )
            return native_snapshot
        except Exception as exc:  # pragma: no cover - exercised by live WebView2
            self._fail(f"WebView2 运行失败：{exc}")
            return None

    def on_closed(self) -> None:
        self._stop.set()

    def on_closing(self) -> bool | None:
        """Defer the first close until the WebView snapshot is safely persisted."""
        if not self.preview_mode or self._preview is None:
            self._stop.set()
            return

        with self._lock:
            if self._allow_close:
                self._stop.set()
                return None
            if self._close_save_started:
                return False
            self._close_save_started = True

        threading.Thread(
            target=self._save_snapshot_and_close,
            name="preview-close-save",
            daemon=True,
        ).start()
        return False

    def _save_snapshot_and_close(self) -> None:
        try:
            snapshot = self._evaluate("window.notebookPreview.snapshotForClose()")
            if isinstance(snapshot, dict) and self._preview is not None:
                self._preview.save_note(str(snapshot.get("work_note", "")))
                theme = snapshot.get("reading_theme")
                if isinstance(theme, str):
                    self._preview.save_theme(theme)
                book_id = snapshot.get("book_id")
                position = snapshot.get("char_position")
                if isinstance(book_id, str) and isinstance(position, (int, float)):
                    self.save_position(book_id, int(position))
        except Exception:
            logging.exception("关闭测试版时保存最终状态失败")
        finally:
            with self._lock:
                self._allow_close = True
            self._stop.set()
            if self.window is not None:
                try:
                    self.window.destroy()
                except Exception:
                    logging.exception("保存最终状态后关闭测试版失败")

    def preview_snapshot(self) -> dict[str, Any]:
        if self._preview is None:
            return {"enabled": False}
        return self._preview.snapshot()

    @contextmanager
    def dialog_guard(self) -> Any:
        """Pause native hover sampling only while an OS dialog owns interaction."""
        with self._lock:
            self._dialog_depth += 1
            self._inside_since = None
        try:
            yield
        finally:
            with self._lock:
                self._dialog_depth = max(0, self._dialog_depth - 1)
                self._dialog_guard_until = time.perf_counter() + 0.2
                self._inside_since = None
                if self._probe is not None:
                    try:
                        self._last_inside = bool(self._probe.snapshot()["inside"])
                    except Exception:
                        self._last_inside = None

    def select_novel(self, intent: str) -> dict[str, Any]:
        assert self.window is not None
        normalized_intent = "open" if intent == "open" else "add"
        try:
            with self.dialog_guard():
                selected = self.window.create_file_dialog(
                    webview.FileDialog.OPEN,
                    allow_multiple=False,
                    file_types=(tr("dialog_file_type"),),
                )
                if not selected:
                    return {
                        "ok": False,
                        "cancelled": True,
                        "message": tr("dialog_cancelled"),
                    }
                selected_path = Path(selected[0])
                if self._preview is not None:
                    record = self._preview.add_book(selected_path)
                    metadata = (
                        self.prepare_preview_book(record["book_id"])
                        if normalized_intent == "open"
                        else record
                    )
                else:
                    metadata = self._library.open_path(selected_path)
            if normalized_intent == "open":
                self._set_mode("read", "explicit-file-open")
            return {
                "ok": True,
                "cancelled": False,
                "intent": normalized_intent,
                "book": metadata,
                "message": tr("dialog_opened", title=metadata["title"]),
            }
        except (NovelEngineError, PreviewStorageError) as error:
            return {"ok": False, "cancelled": False, "error": str(error)}

    def prepare_preview_book(self, book_id: str) -> dict[str, Any]:
        if self._preview is None:
            return self._library.metadata(book_id)
        record = self._preview.record(book_id)
        source = Path(record.file_path)
        if not source.is_file():
            raise PreviewStorageError(tr("preview_file_missing"))
        normalized_path = str(source.resolve(strict=False)).casefold()
        internal_id = self._preview_library_ids.get(book_id)
        if (
            internal_id is None
            or self._preview_library_paths.get(book_id) != normalized_path
        ):
            loaded = self._library.open_path(source)
            internal_id = str(loaded["book_id"])
            self._preview_library_ids[book_id] = internal_id
            self._preview_library_paths[book_id] = normalized_path
        self._library.save_position(internal_id, record.char_position)
        metadata = self._library.metadata(internal_id)
        metadata.update(
            {
                "book_id": book_id,
                "title": record.display_title,
                "path": record.file_path,
                "persisted": True,
            }
        )
        return metadata

    def commit_preview_book(self, book_id: str) -> dict[str, Any]:
        if self._preview is None:
            return self._library.metadata(book_id)
        internal_id = self._preview_library_ids.get(book_id)
        if internal_id is None:
            raise PreviewStorageError(tr("preview_book_not_found"))
        return self._preview.activate_loaded(
            book_id, self._library.metadata(internal_id)
        )

    def render_payload(self, book_id: str) -> dict[str, Any]:
        internal_id = self._preview_library_ids.get(book_id, book_id)
        payload = self._library.render_payload(internal_id)
        if self._preview is not None:
            record = self._preview.record(book_id)
            payload.update(
                {
                    "book_id": book_id,
                    "title": record.display_title,
                    "path": record.file_path,
                    "char_position": record.char_position,
                    "persisted": True,
                }
            )
        return payload

    def save_position(self, book_id: str, position: int) -> dict[str, Any]:
        internal_id = self._preview_library_ids.get(book_id, book_id)
        metadata = self._library.save_position(internal_id, position)
        if self._preview is None:
            return metadata
        metadata["book_id"] = book_id
        return self._preview.save_position(book_id, metadata)

    def rename_preview_book(self, book_id: str, title: str) -> dict[str, Any]:
        if self._preview is None:
            raise PreviewStorageError(tr("preview_book_not_found"))
        return self._preview.rename_book(book_id, title)

    def relocate_preview_book(self, book_id: str) -> dict[str, Any]:
        if self._preview is None or self.window is None:
            raise PreviewStorageError(tr("preview_book_not_found"))
        record = self._preview.record(book_id)
        extension = record.file_format.lower()
        with self.dialog_guard():
            selected = self.window.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=(
                    tr(
                        "preview_relocate_type",
                        format=extension.upper(),
                        extension=extension,
                    ),
                ),
            )
        if not selected:
            return {"ok": False, "cancelled": True}
        updated = self._preview.relocate_book(book_id, Path(selected[0]))
        return {"ok": True, "cancelled": False, "book": updated}

    def remove_preview_book(self, book_id: str) -> dict[str, Any]:
        if self._preview is None:
            raise PreviewStorageError(tr("preview_book_not_found"))
        result = self._preview.remove_book(book_id)
        self._preview_library_ids.pop(book_id, None)
        self._preview_library_paths.pop(book_id, None)
        return result

    def save_preview_theme(self, theme: str) -> dict[str, Any]:
        if self._preview is None:
            return {"reading_theme": "classic"}
        return {"reading_theme": self._preview.save_theme(theme)}

    def save_preview_note(self, content: str) -> dict[str, Any]:
        if self._preview is None:
            return {"saved": False}
        return {"saved": self._preview.save_note(content)}

    def enable_hover(self) -> dict[str, Any]:
        with self._lock:
            self.hover_reading_enabled = True
            self._last_inside = None
            self._inside_since = None
        return {
            "ok": True,
            "message": tr("hover_enabled"),
        }

    def disable_hover(self) -> dict[str, Any]:
        with self._lock:
            self.hover_reading_enabled = False
            self._last_inside = None
            self._inside_since = None
        self._set_mode("work", "alt-q")
        return {"ok": True, "message": tr("hover_disabled")}

    def _monitor_pointer(self) -> None:
        assert self._probe is not None
        while not self._stop.wait(POINTER_POLL_SECONDS):
            snapshot = self._probe.snapshot()
            inside = bool(snapshot["inside"])
            next_mode = self._process_pointer_sample(inside, time.perf_counter())
            if next_mode is not None:
                self._set_mode(next_mode, "native-window-hover")

    def _process_pointer_sample(self, inside: bool, now: float) -> str | None:
        with self._lock:
            if self._dialog_depth or now < self._dialog_guard_until:
                self._last_inside = inside
                self._inside_since = None
                return None
            if not self.hover_reading_enabled:
                self._last_inside = inside
                self._inside_since = None
                return None
            next_mode: str | None = None
            if inside:
                if self._last_inside is not True:
                    self._inside_since = now
                if (
                    self.app_mode == "work"
                    and self._inside_since is not None
                    and now - self._inside_since >= ENTER_DELAY_SECONDS
                ):
                    next_mode = "read"
            else:
                self._inside_since = None
                if self.app_mode == "read":
                    next_mode = "work"
            self._last_inside = inside
            return next_mode

    def _set_mode(self, mode: str, source: str) -> None:
        normalized = "read" if mode == "read" else "work"
        with self._lock:
            if self.app_mode == normalized and source != "startup":
                return
            self.app_mode = normalized
        self._evaluate(
            "window.notebookPoc.setAppMode"
            f"({json.dumps(normalized)}, {json.dumps(source)})"
        )

    def _notify_frontend(self, payload: dict[str, Any]) -> None:
        self._evaluate(
            "window.notebookPoc.onPythonNotification"
            f"({json.dumps(payload, ensure_ascii=False)})"
        )

    def _evaluate(self, script: str) -> Any:
        if self.window is None:
            raise RuntimeError("pywebview window is not attached.")
        return self.window.evaluate_js(script)

    def _fail(self, message: str) -> None:
        self.run_error = message
        logging.error(message)
        try:
            self._notify_frontend({"ok": False, "message": message})
        except Exception:
            logging.exception("无法把错误显示到 WebView2 前端")


class WebViewApi:
    def __init__(self, controller: WebViewController) -> None:
        # pywebview recursively exposes public attributes on js_api objects.
        # Keep the controller private so Window.native/.NET objects are never scanned.
        self._controller = controller

    def enable_hover_reading(self) -> dict[str, Any]:
        return self._controller.enable_hover()

    def disable_hover_reading(self) -> dict[str, Any]:
        return self._controller.disable_hover()

    @staticmethod
    def _ascii_json(value: dict[str, Any]) -> str:
        """Use an ASCII envelope to bypass pythonnet's Windows ANSI marshalling."""
        encoded = json.dumps(
            value, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return "b64:" + base64.b64encode(encoded).decode("ascii")

    def select_novel(self, intent: str = "open") -> str:
        return self._ascii_json(self._controller.select_novel(intent))

    def prepare_preview_book(self, book_id: str) -> str:
        return self._ascii_json(self._controller.prepare_preview_book(book_id))

    def commit_preview_book(self, book_id: str) -> str:
        return self._ascii_json(self._controller.commit_preview_book(book_id))

    def get_render_payload(self, book_id: str) -> str:
        return self._ascii_json(self._controller.render_payload(book_id))

    def save_position(self, book_id: str, char_position: int) -> str:
        return self._ascii_json(self._controller.save_position(book_id, char_position))

    def rename_preview_book(self, book_id: str, title: str) -> str:
        return self._ascii_json(
            self._controller.rename_preview_book(book_id, title)
        )

    def relocate_preview_book(self, book_id: str) -> str:
        return self._ascii_json(self._controller.relocate_preview_book(book_id))

    def remove_preview_book(self, book_id: str) -> str:
        return self._ascii_json(self._controller.remove_preview_book(book_id))

    def save_preview_theme(self, theme: str) -> str:
        return self._ascii_json(self._controller.save_preview_theme(theme))

    def save_preview_note(self, content: str) -> str:
        return self._ascii_json(self._controller.save_preview_note(content))


__all__ = [
    "APP_TITLE",
    "ENTER_DELAY_SECONDS",
    "NativeWindowProbe",
    "POINTER_POLL_SECONDS",
    "WebViewApi",
    "WebViewController",
    "WINDOW_HEIGHT",
    "WINDOW_MIN_SIZE",
    "WINDOW_WIDTH",
    "detect_webview2_runtime",
    "point_in_rect",
]
