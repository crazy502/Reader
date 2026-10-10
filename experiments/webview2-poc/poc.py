"""Independent pywebview/WebView2 proof of concept for Notebook."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

import webview


TITLE = "Notebook WebView2 PoC"
WINDOW_WIDTH = 760
WINDOW_HEIGHT = 620
WINDOW_MIN_SIZE = (470, 360)
ENTER_DELAY_SECONDS = 0.4
POINTER_POLL_SECONDS = 0.04
EXPERIMENT_ROOT = Path(__file__).resolve().parent
INDEX_PATH = EXPERIMENT_ROOT / "web" / "index.html"


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


class PocController:
    def __init__(self, *, smoke_test: bool = False) -> None:
        self.window: webview.Window | None = None
        self.smoke_test = smoke_test
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
            if self.smoke_test:
                self._run_smoke_test(native_snapshot)
                return
            self._monitor_pointer()
        except Exception as exc:  # pragma: no cover - exercised by live PoC
            self._fail(f"PoC 运行失败：{exc}")

    def on_closed(self) -> None:
        self._stop.set()

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
        }

    def enable_hover(self) -> dict[str, Any]:
        with self._lock:
            self.hover_reading_enabled = True
            self._last_inside = None
            self._inside_since = None
        return {
            "ok": True,
            "message": "悬停阅读已启用；进入窗口约 400ms 后显示阅读区域。",
        }

    def disable_hover(self) -> dict[str, Any]:
        with self._lock:
            self.hover_reading_enabled = False
            self._last_inside = None
            self._inside_since = None
        self._set_mode("work", "alt-q")
        return {"ok": True, "message": "Alt+Q：已禁用悬停阅读并返回工作模式。"}

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

    def enable_hover_reading(self) -> dict[str, Any]:
        return self._controller.enable_hover()

    def disable_hover_reading(self) -> dict[str, Any]:
        return self._controller.disable_hover()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="运行实际 WebView2/JS bridge 冒烟检查并自动关闭窗口",
    )
    parser.add_argument("--debug", action="store_true", help="启用 pywebview 调试输出")
    return parser.parse_args()


def main() -> int:
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
    controller = PocController(smoke_test=args.smoke_test)
    api = PocApi(controller)
    window = webview.create_window(
        TITLE,
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
    window.events.closed += controller.on_closed

    webview.start(
        func=controller.run,
        gui="edgechromium",
        debug=args.debug,
        private_mode=True,
    )
    if controller.smoke_error:
        print(controller.smoke_error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
