"""Source entry point for the Notebook WebView2 application."""

from __future__ import annotations

import argparse
import ctypes
import logging
from pathlib import Path
import sys

import webview

from .controller import (
    APP_TITLE,
    WebViewApi,
    WebViewController,
    WINDOW_HEIGHT,
    WINDOW_MIN_SIZE,
    WINDOW_WIDTH,
    detect_webview2_runtime,
)
from .i18n import tr


WEBVIEW_ROOT = Path(__file__).resolve().parent


def resolve_web_root() -> Path:
    """Locate the packaged or source WebView2 assets."""
    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        root = Path(bundle_root)
        candidates.extend(
            [
                root / "reader" / "webview" / "web",
            ]
        )
    candidates.append(WEBVIEW_ROOT / "web")
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return candidates[0]


def create_app_window(
    *,
    data_dir: Path | None = None,
    index_path: Path | None = None,
) -> tuple[WebViewController, webview.Window]:
    """Create and wire the WebView2 window without starting the GUI loop."""
    page = index_path or (resolve_web_root() / "index.html")
    if not page.is_file():
        raise FileNotFoundError(f"找不到 WebView2 页面：{page}")
    controller = WebViewController(data_dir=data_dir)
    api = WebViewApi(controller)
    window = webview.create_window(
        APP_TITLE,
        url=str(page),
        js_api=api,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=WINDOW_MIN_SIZE,
        resizable=True,
        background_color="#F7F5F0",
        text_select=True,
    )
    if window is None:
        raise RuntimeError("pywebview 未能创建窗口。")
    controller.attach(window)
    window.events.closing += controller.on_closing
    window.events.closed += controller.on_closed
    return controller, window


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--debug", action="store_true", help="启用 pywebview 调试输出")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if sys.platform != "win32":
        print("Notebook WebView2 仅支持 Windows。", file=sys.stderr)
        return 2
    runtime = detect_webview2_runtime()
    if not runtime["executable"]:
        ctypes.windll.user32.MessageBoxW(
            None,
            tr("runtime_missing"),
            tr("runtime_title"),
            0x10,
        )
        return 2
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        controller, _window = create_app_window()
    except (FileNotFoundError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    webview.start(
        func=controller.run,
        gui="edgechromium",
        debug=args.debug,
        private_mode=True,
    )
    if controller.run_error:
        print(controller.run_error, file=sys.stderr)
        return 1
    return 0


__all__ = ["create_app_window", "main", "resolve_web_root"]
