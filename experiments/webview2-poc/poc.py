"""Independent pywebview/WebView2 proof of concept for Notebook."""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from typing import Any

import webview

from novel_engine import ExperimentLibrary, ExperimentNovelError
from preview_storage import PreviewStorage, PreviewStorageError
from sample_data import write_generated_epub, write_generated_txt
from src.i18n import tr


POC_TITLE = "Notebook WebView2 PoC"
PREVIEW_TITLE = tr("preview_title")
TITLE = POC_TITLE
WINDOW_WIDTH = 760
WINDOW_HEIGHT = 620
WINDOW_MIN_SIZE = (470, 360)
ENTER_DELAY_SECONDS = 0.4
POINTER_POLL_SECONDS = 0.04
EXPERIMENT_ROOT = Path(__file__).resolve().parent
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", EXPERIMENT_ROOT))
INDEX_PATH = BUNDLE_ROOT / "web" / "index.html"
REPORTS_DIR = EXPERIMENT_ROOT / "reports"


class Point(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class Rect(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class ProcessEntry32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def point_in_rect(point: Point, rect: Rect) -> bool:
    return rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom


def process_tree_metrics(root_pid: int | None = None) -> dict[str, Any]:
    """Measure this Python process and all current WebView2 descendants.

    The result is a point-in-time working-set/CPU sample.  It is intentionally
    best-effort because some protected Edge helper processes may deny access.
    """
    if sys.platform != "win32":
        return {"available": False, "reason": "Windows-only process probe"}
    root = os.getpid() if root_pid is None else int(root_pid)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry32W),
    ]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry32W),
    ]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid_handle = wintypes.HANDLE(-1).value
    if snapshot == invalid_handle:
        return {"available": False, "reason": "CreateToolhelp32Snapshot failed"}

    entries: dict[int, tuple[int, str]] = {}
    entry = ProcessEntry32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                entries[int(entry.th32ProcessID)] = (
                    int(entry.th32ParentProcessID),
                    str(entry.szExeFile),
                )
                entry.dwSize = ctypes.sizeof(entry)
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)

    descendants = {root}
    changed = True
    while changed:
        changed = False
        for pid, (parent, _name) in entries.items():
            if parent in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True

    processes: list[dict[str, Any]] = []
    for pid in sorted(descendants):
        handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
        if not handle:
            continue
        try:
            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), ctypes.sizeof(counters)
            ):
                continue
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            cpu_seconds: float | None = None
            if kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                kernel_ticks = (kernel.dwHighDateTime << 32) | kernel.dwLowDateTime
                user_ticks = (user.dwHighDateTime << 32) | user.dwLowDateTime
                cpu_seconds = (kernel_ticks + user_ticks) / 10_000_000
            processes.append(
                {
                    "pid": pid,
                    "name": entries.get(pid, (0, "unknown"))[1],
                    "rss_bytes": int(counters.WorkingSetSize),
                    "cpu_seconds": cpu_seconds,
                    "role": "python" if pid == root else "child",
                }
            )
        finally:
            kernel32.CloseHandle(handle)

    return {
        "available": bool(processes),
        "root_pid": root,
        "process_count": len(processes),
        "rss_bytes": sum(process["rss_bytes"] for process in processes),
        "python_rss_bytes": sum(
            process["rss_bytes"] for process in processes if process["role"] == "python"
        ),
        "child_rss_bytes": sum(
            process["rss_bytes"] for process in processes if process["role"] == "child"
        ),
        "cpu_seconds": sum(
            process["cpu_seconds"] or 0.0 for process in processes
        ),
        "processes": processes,
    }


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


class PocController:
    def __init__(
        self,
        *,
        smoke_test: bool = False,
        phase2_smoke: bool = False,
        benchmark_sizes: tuple[int, ...] = (),
        benchmark_runs: int = 3,
        preview_mode: bool = False,
        preview_data_dir: Path | None = None,
        preview_smoke: bool = False,
    ) -> None:
        self.window: webview.Window | None = None
        self.smoke_test = smoke_test
        self.phase2_smoke = phase2_smoke
        self.benchmark_sizes = benchmark_sizes
        self.benchmark_runs = benchmark_runs
        self.preview_mode = preview_mode
        self.preview_smoke = preview_smoke
        self.smoke_error: str | None = None
        self.smoke_result: dict[str, Any] | None = None
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
        self._library = ExperimentLibrary()
        self._preview = PreviewStorage(preview_data_dir) if preview_mode else None
        self._preview_library_ids: dict[str, str] = {}
        self._preview_library_paths: dict[str, str] = {}

    def attach(self, window: webview.Window) -> None:
        self.window = window

    def run(self) -> None:
        assert self.window is not None
        if not self.window.events.loaded.wait(20):
            self._fail("HTML 页面在 20 秒内未完成加载。")
            return

        self.renderer = str(webview.renderer or "unknown")
        if self.renderer != "edgechromium":
            self._fail(f"实际 GUI 后端为 {self.renderer}，拒绝将其视为 WebView2 验证。")
            return

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
            if self.preview_smoke:
                self._run_preview_smoke(native_snapshot)
                return
            if self.smoke_test:
                self._run_smoke_test(native_snapshot)
                return
            if self.phase2_smoke:
                self._run_phase2_job((120_000,), 1, "phase2-smoke")
                return
            if self.benchmark_sizes:
                self._run_phase2_job(
                    self.benchmark_sizes, self.benchmark_runs, "phase2-benchmark"
                )
                return
            self._monitor_pointer()
        except Exception as exc:  # pragma: no cover - exercised by live PoC
            self._fail(f"PoC 运行失败：{exc}")

    def on_closed(self) -> None:
        self._stop.set()

    def on_closing(self) -> None:
        """Synchronously capture the latest anchors before WebView destruction."""
        if not self.preview_mode or self._preview is None:
            return
        try:
            snapshot = self._evaluate("window.notebookPreview.snapshotForClose()")
            if not isinstance(snapshot, dict):
                return
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

    def app_info(self) -> dict[str, Any]:
        return {
            "app": TITLE,
            "python": sys.version.split()[0],
            "pywebview": version("pywebview"),
            "renderer": self.renderer,
            "webview2_runtime": self.runtime,
            "hover": {
                "enabled": self.hover_reading_enabled,
                "enter_delay_ms": int(ENTER_DELAY_SECONDS * 1000),
                "native_poll_ms": int(POINTER_POLL_SECONDS * 1000),
                "app_mode": self.app_mode,
            },
            "preview": {
                "enabled": self.preview_mode,
                "data_dir": (
                    str(self._preview.data_dir) if self._preview is not None else None
                ),
            },
        }

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
        except (ExperimentNovelError, PreviewStorageError) as error:
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

    def render_payload(self, book_id: str, strategy: str) -> dict[str, Any]:
        normalized = "whole" if strategy == "whole" else "chunked"
        internal_id = self._preview_library_ids.get(book_id, book_id)
        payload = self._library.render_payload(internal_id, normalized)
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

    def book_state(self, book_id: str) -> dict[str, Any]:
        if self._preview is None:
            return self._library.metadata(book_id)
        record = self._preview.record(book_id)
        return self._preview._book_json(record)

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

    def prepare_synthetic(
        self, target_chars: int, parse_runs: int = 3
    ) -> dict[str, Any]:
        return self._library.prepare_synthetic(target_chars, parse_runs=parse_runs)

    def prepare_generated_format_samples(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(
            prefix="notebook-webview-formats-", dir=EXPERIMENT_ROOT
        ) as temporary:
            root = Path(temporary)
            txt = self._library.open_path(write_generated_txt(root / "sample.txt"))
            epub = self._library.open_path(write_generated_epub(root / "sample.epub"))
        return {"generated_samples": True, "txt": txt, "epub": epub}

    def seed_preview_smoke(self, root: Path) -> None:
        if self._preview is None:
            raise RuntimeError("Preview storage is not enabled.")
        root.mkdir(parents=True, exist_ok=True)
        self._preview.add_book(write_generated_txt(root / "preview-a.txt"))
        self._preview.add_book(write_generated_epub(root / "preview-b.epub"))
        self._preview.save_note("WebView2 测试版便笺🙂")

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

    def _run_smoke_test(self, native_snapshot: dict[str, Any]) -> None:
        assert self.window is not None
        hover = self._run_native_hover_smoke()
        prototype = self._evaluate("window.notebookPoc.runPrototypeSmoke()")
        self._evaluate("window.notebookPoc.runBridgeTest(); true")

        deadline = time.perf_counter() + 8
        bridge_result: Any = None
        bridge_state = "pending"
        while time.perf_counter() < deadline:
            state = self._evaluate("window.notebookPoc.getState()")
            bridge_state = str(state.get("bridgeState", "pending"))
            if bridge_state in {"ok", "error"}:
                bridge_result = self._evaluate("window.notebookPoc.getBridgeResult()")
                break
            time.sleep(0.05)

        self.window.resize(730, 560)
        time.sleep(0.15)
        narrow = self._evaluate(
            "({width: window.innerWidth, height: window.innerHeight, "
            "columns: getComputedStyle(document.getElementById('bookGrid')).gridTemplateColumns})"
        )
        self.window.resize(1000, 700)
        time.sleep(0.15)
        wide = self._evaluate(
            "({width: window.innerWidth, height: window.innerHeight, "
            "columns: getComputedStyle(document.getElementById('bookGrid')).gridTemplateColumns})"
        )

        final_state = self._evaluate("window.notebookPoc.getState()")
        success = bool(
            isinstance(prototype, dict)
            and prototype.get("allPassed")
            and bridge_state == "ok"
            and isinstance(bridge_result, dict)
            and bridge_result.get("ping", {}).get("reply") == "pong"
            and hover.get("ok")
        )
        self.smoke_result = {
            "ok": success,
            "renderer": self.renderer,
            "runtime": self.runtime,
            "native_window": native_snapshot,
            "native_hover": hover,
            "prototype": prototype,
            "bridge": bridge_result,
            "narrow": narrow,
            "wide": wide,
            "final_state": final_state,
        }
        print("POC_SMOKE_RESULT=" + json.dumps(self.smoke_result, ensure_ascii=False), flush=True)
        if not success:
            self.smoke_error = "自动冒烟检查未全部通过。"
        self.window.destroy()

    def _run_preview_smoke(self, native_snapshot: dict[str, Any]) -> None:
        assert self.window is not None
        assert self._preview is not None
        self._set_mode("read", "preview-smoke")
        self._evaluate(
            "window.notebookPhase2.runPreviewIntegrationSmoke()"
            ".catch(() => undefined); true"
        )
        deadline = time.perf_counter() + 120
        frontend_state: dict[str, Any] = {"status": "starting"}
        while time.perf_counter() < deadline:
            frontend_state = self._evaluate(
                "window.notebookPhase2.getPreviewSmokeState()"
            )
            if frontend_state.get("status") in {"complete", "error"}:
                break
            time.sleep(0.1)
        result = frontend_state.get("result")
        restored = PreviewStorage(self._preview.data_dir).snapshot()
        books = restored["books"]
        positions = [int(book["char_position"]) for book in books]
        success = bool(
            isinstance(result, dict)
            and result.get("ok")
            and frontend_state.get("status") == "complete"
            and len(books) == 2
            and all(position > 0 for position in positions)
            and len(set(positions)) == 2
            and restored["reading_theme"] == "eye_care"
            and restored["work_note"] == "WebView2 测试版便笺🙂"
        )
        self.smoke_result = {
            "ok": success,
            "renderer": self.renderer,
            "runtime": self.runtime,
            "native_window": native_snapshot,
            "frontend": result,
            "frontend_state": frontend_state,
            "restart_snapshot": restored,
        }
        print(
            "PREVIEW_SMOKE_RESULT="
            + json.dumps(self.smoke_result, ensure_ascii=True),
            flush=True,
        )
        if not success:
            self.smoke_error = "WebView2 可用测试版冒烟检查未全部通过。"
        self.window.destroy()

    def _run_native_hover_smoke(self) -> dict[str, Any]:
        assert self.window is not None
        assert self._probe is not None
        original = self._probe.snapshot()
        screen = self._probe.virtual_screen()
        rect = original["rect"]
        cursor = original["cursor"]
        width = rect["right"] - rect["left"]
        height = rect["bottom"] - rect["top"]
        scale = max(0.5, width / WINDOW_WIDTH)
        screen_right = screen["left"] + screen["width"]
        screen_bottom = screen["top"] + screen["height"]

        inside_left = min(
            max(cursor["x"] - width // 2, screen["left"]),
            max(screen["left"], screen_right - width),
        )
        inside_top = min(
            max(cursor["y"] - height // 2, screen["top"]),
            max(screen["top"], screen_bottom - height),
        )
        self.window.move(round(inside_left / scale), round(inside_top / scale))
        inside_snapshot = self._wait_for_pointer_state(True)

        self.enable_hover()
        enter_started = time.perf_counter()
        while self.app_mode != "read" and time.perf_counter() - enter_started < 1.5:
            sample = self._probe.snapshot()
            next_mode = self._process_pointer_sample(
                bool(sample["inside"]), time.perf_counter()
            )
            if next_mode is not None:
                self._set_mode(next_mode, "native-hover-smoke")
            time.sleep(POINTER_POLL_SECONDS)
        enter_ms = (time.perf_counter() - enter_started) * 1000

        corner_candidates = [
            (screen["left"], screen["top"]),
            (max(screen["left"], screen_right - width), screen["top"]),
            (screen["left"], max(screen["top"], screen_bottom - height)),
            (
                max(screen["left"], screen_right - width),
                max(screen["top"], screen_bottom - height),
            ),
        ]
        outside_left, outside_top = next(
            (
                (left, top)
                for left, top in corner_candidates
                if not (
                    left <= cursor["x"] < left + width
                    and top <= cursor["y"] < top + height
                )
            ),
            corner_candidates[0],
        )
        exit_started = time.perf_counter()
        self.window.move(round(outside_left / scale), round(outside_top / scale))
        outside_snapshot = self._wait_for_pointer_state(False)
        next_mode = self._process_pointer_sample(False, time.perf_counter())
        if next_mode is not None:
            self._set_mode(next_mode, "native-hover-smoke")
        exit_ms = (time.perf_counter() - exit_started) * 1000

        self.disable_hover()
        self.window.move(round(rect["left"] / scale), round(rect["top"] / scale))
        return {
            "ok": (
                bool(inside_snapshot["inside"])
                and not bool(outside_snapshot["inside"])
                and self.app_mode == "work"
                and enter_ms >= ENTER_DELAY_SECONDS * 1000
                and enter_ms < 800
                and exit_ms < 250
            ),
            "enter_ms": round(enter_ms, 1),
            "exit_ms": round(exit_ms, 1),
            "configured_enter_ms": int(ENTER_DELAY_SECONDS * 1000),
            "poll_ms": int(POINTER_POLL_SECONDS * 1000),
            "inside_snapshot": inside_snapshot,
            "outside_snapshot": outside_snapshot,
        }

    def _wait_for_pointer_state(self, expected: bool) -> dict[str, Any]:
        assert self._probe is not None
        deadline = time.perf_counter() + 2
        latest = self._probe.snapshot()
        while bool(latest["inside"]) != expected and time.perf_counter() < deadline:
            time.sleep(0.02)
            latest = self._probe.snapshot()
        if bool(latest["inside"]) != expected:
            raise RuntimeError(f"无法将原生窗口移动到 inside={expected} 的测试位置。")
        return latest

    def _run_phase2_job(
        self, sizes: tuple[int, ...], repeats: int, report_name: str
    ) -> None:
        assert self.window is not None
        self._set_mode("read", report_name)
        expression = (
            "window.notebookPhase2.runAutomatedBenchmark("
            + json.dumps({"sizes": list(sizes), "repeats": repeats})
            + ").catch(() => undefined); true"
        )
        self._evaluate(expression)
        deadline = time.perf_counter() + 20 * 60
        latest: dict[str, Any] = {"status": "starting"}
        while time.perf_counter() < deadline:
            latest = self._evaluate("window.notebookPhase2.getBenchmarkState()")
            if latest.get("status") in {"complete", "error"}:
                break
            time.sleep(0.1)
        if latest.get("status") != "complete":
            self.smoke_error = str(
                latest.get("error") or "Phase 2 browser benchmark timed out"
            )
            print(
                "PHASE2_BENCHMARK_ERROR="
                + json.dumps(latest, ensure_ascii=False),
                flush=True,
            )
            self.window.destroy()
            return

        result = latest["result"]
        resize_stability = self._run_resize_stability_check()
        result["window_resize_stability"] = resize_stability
        result["renderer"] = self.renderer
        result["webview2_runtime"] = self.runtime
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / f"latest-{report_name}.json"
        report_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            "PHASE2_BENCHMARK_RESULT=" + json.dumps(result, ensure_ascii=False),
            flush=True,
        )
        print(f"PHASE2_BENCHMARK_REPORT={report_path}", flush=True)
        self.window.destroy()

    def _run_resize_stability_check(self) -> dict[str, Any]:
        assert self.window is not None
        anchor = int(self._evaluate("window.notebookPhase2.topCharPosition()"))
        checks: list[dict[str, Any]] = []
        for width, height in ((730, 560), (1000, 700), (760, 620)):
            self.window.resize(width, height)
            time.sleep(0.2)
            self._evaluate(
                "window.notebookPhase2.restorePosition("
                + str(anchor)
                + ").catch(() => undefined); true"
            )
            time.sleep(0.25)
            actual = int(self._evaluate("window.notebookPhase2.topCharPosition()"))
            checks.append(
                {
                    "window": [width, height],
                    "requested": anchor,
                    "actual": actual,
                    "error_chars": abs(actual - anchor),
                }
            )
        return {"anchor": anchor, "checks": checks}

    def _fail(self, message: str) -> None:
        self.smoke_error = message
        logging.error(message)
        try:
            self._notify_frontend({"ok": False, "message": message})
        except Exception:
            logging.exception("无法把错误显示到 PoC 前端")
        if self.smoke_test and self.window is not None:
            self.window.destroy()


class PocApi:
    def __init__(self, controller: PocController) -> None:
        # pywebview recursively exposes public attributes on js_api objects.
        # Keep the controller private so Window.native/.NET objects are never scanned.
        self._controller = controller

    def ping(self, message: str = "") -> dict[str, Any]:
        return {
            "ok": True,
            "reply": "pong",
            "echo": str(message),
            "thread": threading.current_thread().name,
            "timestamp": time.time(),
        }

    def get_app_info(self) -> dict[str, Any]:
        return self._controller.app_info()

    def get_preview_state(self) -> str:
        return self._ascii_json(self._controller.preview_snapshot())

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

    def get_render_payload(self, book_id: str, strategy: str) -> str:
        return self._ascii_json(self._controller.render_payload(book_id, strategy))

    def save_position(self, book_id: str, char_position: int) -> str:
        return self._ascii_json(self._controller.save_position(book_id, char_position))

    def get_book_state(self, book_id: str) -> str:
        return self._ascii_json(self._controller.book_state(book_id))

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

    def prepare_synthetic_book(
        self, target_chars: int, parse_runs: int = 3
    ) -> str:
        return self._ascii_json(
            self._controller.prepare_synthetic(target_chars, parse_runs)
        )

    def get_process_metrics(self) -> str:
        return self._ascii_json(process_tree_metrics())

    def prepare_generated_format_samples(self) -> str:
        return self._ascii_json(
            self._controller.prepare_generated_format_samples()
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="运行实际 WebView2/JS bridge 冒烟检查并自动关闭窗口",
    )
    parser.add_argument(
        "--phase2-smoke",
        action="store_true",
        help=tr("phase2_smoke_help"),
    )
    parser.add_argument(
        "--preview-smoke",
        action="store_true",
        help="在隔离临时目录运行可用测试版的双书持久化冒烟检查",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help=tr("benchmark_help"),
    )
    parser.add_argument(
        "--benchmark-runs",
        type=int,
        default=3,
        help=tr("benchmark_runs_help"),
    )
    parser.add_argument(
        "--benchmark-sizes",
        default="500000,1000000,3000000",
        help=tr("benchmark_sizes_help"),
    )
    parser.add_argument("--debug", action="store_true", help="启用 pywebview 调试输出")
    return parser.parse_args()


def main(*, preview_mode: bool = False) -> int:
    args = parse_args()
    if sys.platform != "win32":
        print("此 PoC 仅验证 Windows WebView2。", file=sys.stderr)
        return 2
    if not INDEX_PATH.is_file():
        print(f"找不到实验页面：{INDEX_PATH}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        benchmark_sizes = (
            tuple(
                int(value.strip())
                for value in args.benchmark_sizes.split(",")
                if value.strip()
            )
            if args.benchmark
            else ()
        )
    except ValueError:
        print(tr("invalid_benchmark_sizes"), file=sys.stderr)
        return 2
    effective_preview_mode = preview_mode or args.preview_smoke
    runtime = detect_webview2_runtime()
    if effective_preview_mode and not runtime["executable"]:
        ctypes.windll.user32.MessageBoxW(
            None,
            tr("preview_runtime_missing"),
            tr("preview_runtime_title"),
            0x10,
        )
        return 2
    preview_temporary: tempfile.TemporaryDirectory[str] | None = None
    preview_data_dir: Path | None = None
    if args.preview_smoke:
        preview_temporary = tempfile.TemporaryDirectory(
            prefix="notebook-web-preview-smoke-"
        )
        preview_data_dir = Path(preview_temporary.name) / "data"
    controller = PocController(
        smoke_test=args.smoke_test,
        phase2_smoke=args.phase2_smoke,
        benchmark_sizes=benchmark_sizes,
        benchmark_runs=max(1, args.benchmark_runs),
        preview_mode=effective_preview_mode,
        preview_data_dir=preview_data_dir,
        preview_smoke=args.preview_smoke,
    )
    if args.preview_smoke:
        assert preview_temporary is not None
        controller.seed_preview_smoke(Path(preview_temporary.name) / "books")
    api = PocApi(controller)
    window = webview.create_window(
        PREVIEW_TITLE if effective_preview_mode else POC_TITLE,
        url=str(INDEX_PATH),
        js_api=api,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=WINDOW_MIN_SIZE,
        resizable=True,
        background_color="#F7F5F0",
        text_select=True,
    )
    if window is None:
        print("pywebview 未能创建窗口。", file=sys.stderr)
        return 2
    controller.attach(window)
    window.events.closing += controller.on_closing
    window.events.closed += controller.on_closed

    webview.start(
        func=controller.run,
        gui="edgechromium",
        debug=args.debug,
        private_mode=True,
    )
    if controller.smoke_error:
        if preview_temporary is not None:
            preview_temporary.cleanup()
        print(controller.smoke_error, file=sys.stderr)
        return 1
    if preview_temporary is not None:
        preview_temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
