"""Compatibility launcher for the historical WebView2 PoC and benchmarks."""

from __future__ import annotations

import argparse
import ctypes
import logging
from pathlib import Path
import sys
import tempfile
from typing import Any

import webview

from novel_engine import ExperimentLibrary
from reader.webview.app import main as webview_main
from reader.webview.controller import (
    ENTER_DELAY_SECONDS,
    POINTER_POLL_SECONDS,
    WINDOW_HEIGHT,
    WINDOW_MIN_SIZE,
    WINDOW_WIDTH,
    NativeWindowProbe,
    Point,
    Rect,
    WebViewApi,
    WebViewController,
    detect_webview2_runtime,
    point_in_rect,
)
from src.i18n import tr


POC_TITLE = "Notebook WebView2 PoC"
PREVIEW_TITLE = tr("preview_title")
TITLE = POC_TITLE
EXPERIMENT_ROOT = Path(__file__).resolve().parent
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", EXPERIMENT_ROOT))
INDEX_PATH = BUNDLE_ROOT / "web" / "index.html"
REPORTS_DIR = EXPERIMENT_ROOT / "reports"


class PocController(WebViewController):
    """Formal controller with the benchmark-only rendering adapter installed."""

    def __init__(
        self,
        *,
        preview_mode: bool = False,
        preview_data_dir: Path | None = None,
    ) -> None:
        super().__init__(
            preview_mode=preview_mode,
            preview_data_dir=preview_data_dir,
        )
        self._library = ExperimentLibrary()

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


class PreviewApi(WebViewApi):
    """Legacy bridge signature retained for the experiment HTML."""

    def __init__(self, controller: PocController) -> None:
        super().__init__(controller)
        self._controller = controller

    def get_render_payload(self, book_id: str, strategy: str) -> str:
        return self._ascii_json(self._controller.render_payload(book_id, strategy))


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
    experiment_mode = bool(
        not preview_mode
        or args.smoke_test
        or args.phase2_smoke
        or args.preview_smoke
        or args.benchmark
    )
    if not experiment_mode:
        return webview_main(["--debug"] if args.debug else [])

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

    from poc_experiments import PocApi, PocExperimentController

    controller = PocExperimentController(
        smoke_test=args.smoke_test,
        phase2_smoke=args.phase2_smoke,
        benchmark_sizes=benchmark_sizes,
        benchmark_runs=max(1, args.benchmark_runs),
        preview_mode=effective_preview_mode,
        preview_data_dir=preview_data_dir,
        preview_smoke=args.preview_smoke,
    )
    api = PocApi(controller)
    if args.preview_smoke:
        assert preview_temporary is not None
        controller.seed_preview_smoke(Path(preview_temporary.name) / "books")

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
    smoke_error = controller.smoke_error
    if smoke_error:
        if preview_temporary is not None:
            preview_temporary.cleanup()
        print(smoke_error, file=sys.stderr)
        return 1
    if controller.run_error:
        if preview_temporary is not None:
            preview_temporary.cleanup()
        print(controller.run_error, file=sys.stderr)
        return 1
    if preview_temporary is not None:
        preview_temporary.cleanup()
    return 0


__all__ = [
    "ENTER_DELAY_SECONDS",
    "INDEX_PATH",
    "NativeWindowProbe",
    "POC_TITLE",
    "POINTER_POLL_SECONDS",
    "PocController",
    "Point",
    "PreviewApi",
    "REPORTS_DIR",
    "Rect",
    "WINDOW_HEIGHT",
    "WINDOW_MIN_SIZE",
    "WINDOW_WIDTH",
    "detect_webview2_runtime",
    "main",
    "point_in_rect",
]


if __name__ == "__main__":
    raise SystemExit(main())
