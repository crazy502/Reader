"""Historical PoC, smoke-test, and benchmark support for WebView2."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from importlib.metadata import version
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any

from benchmark_engine import prepare_synthetic
from poc import (
    ENTER_DELAY_SECONDS,
    POINTER_POLL_SECONDS,
    POC_TITLE,
    REPORTS_DIR,
    WINDOW_WIDTH,
    PocController,
    PreviewApi,
)
from preview_storage import PreviewStorage
from sample_data import write_generated_epub, write_generated_txt


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


def process_tree_metrics(root_pid: int | None = None) -> dict[str, Any]:
    """Measure the PoC Python process and its current WebView2 descendants."""
    if os.name != "nt":
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
        "cpu_seconds": sum(process["cpu_seconds"] or 0.0 for process in processes),
        "processes": processes,
    }


class PocExperimentController(PocController):
    """Controller extension loaded only for PoC, smoke, and benchmark runs."""

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
        super().__init__(
            preview_mode=preview_mode,
            preview_data_dir=preview_data_dir,
        )
        self.smoke_test = smoke_test
        self.phase2_smoke = phase2_smoke
        self.benchmark_sizes = benchmark_sizes
        self.benchmark_runs = benchmark_runs
        self.preview_smoke = preview_smoke
        self.smoke_error: str | None = None
        self.smoke_result: dict[str, Any] | None = None

    def run(self) -> None:
        native_snapshot = self.initialize()
        if native_snapshot is None:
            self.smoke_error = self.run_error
            if self.window is not None:
                self.window.destroy()
            return
        try:
            if not self.preview_mode:
                self._evaluate("window.notebookPrototype.bootstrapDemo()")
            if self.preview_smoke:
                self._run_preview_smoke(native_snapshot)
            elif self.smoke_test:
                self._run_smoke_test(native_snapshot)
            elif self.phase2_smoke:
                self._run_phase2_job((120_000,), 1, "phase2-smoke")
            elif self.benchmark_sizes:
                self._run_phase2_job(
                    self.benchmark_sizes,
                    self.benchmark_runs,
                    "phase2-benchmark",
                )
            else:
                self._monitor_pointer()
        except Exception as exc:  # pragma: no cover - exercised by live PoC
            self.smoke_error = f"PoC 运行失败：{exc}"
            self._fail(self.smoke_error)
            if self.window is not None:
                self.window.destroy()

    def app_info(self) -> dict[str, Any]:
        return {
            "app": POC_TITLE,
            "python": os.sys.version.split()[0],
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

    def book_state(self, book_id: str) -> dict[str, Any]:
        if self._preview is None:
            return self._library.metadata(book_id)
        return self._preview._book_json(self._preview.record(book_id))

    def prepare_synthetic(
        self, target_chars: int, parse_runs: int = 3
    ) -> dict[str, Any]:
        return prepare_synthetic(
            self._library,
            target_chars,
            parse_runs=parse_runs,
        )

    def prepare_generated_format_samples(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(
            prefix="notebook-webview-formats-", dir=REPORTS_DIR.parent
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
        print(
            "POC_SMOKE_RESULT="
            + json.dumps(self.smoke_result, ensure_ascii=False),
            flush=True,
        )
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
        result["window_resize_stability"] = self._run_resize_stability_check()
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


class PocApi(PreviewApi):
    """Extended bridge exposed only by PoC, smoke, and benchmark runs."""

    def __init__(self, controller: PocExperimentController) -> None:
        super().__init__(controller)
        self._experiment_controller = controller

    def ping(self, message: str = "") -> dict[str, Any]:
        return {
            "ok": True,
            "reply": "pong",
            "echo": str(message),
            "thread": threading.current_thread().name,
            "timestamp": time.time(),
        }

    def get_app_info(self) -> dict[str, Any]:
        return self._experiment_controller.app_info()

    def get_preview_state(self) -> str:
        return self._ascii_json(self._experiment_controller.preview_snapshot())

    def get_book_state(self, book_id: str) -> str:
        return self._ascii_json(self._experiment_controller.book_state(book_id))

    def prepare_synthetic_book(
        self, target_chars: int, parse_runs: int = 3
    ) -> str:
        return self._ascii_json(
            self._experiment_controller.prepare_synthetic(target_chars, parse_runs)
        )

    def get_process_metrics(self) -> str:
        return self._ascii_json(process_tree_metrics())

    def prepare_generated_format_samples(self) -> str:
        return self._ascii_json(
            self._experiment_controller.prepare_generated_format_samples()
        )
