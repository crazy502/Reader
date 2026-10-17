"""Live WebView2 smoke check for the formal ``reader.webview`` entry."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
from typing import Any

import webview


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reader.webview.app import create_app_window
from reader.webview.storage import PreviewStorage
from sample_data import write_generated_txt


def main() -> int:
    result: dict[str, Any] = {"ok": False}
    with tempfile.TemporaryDirectory(
        prefix="notebook-formal-webview-smoke-"
    ) as temporary:
        root = Path(temporary)
        data_dir = root / "data"
        storage = PreviewStorage(data_dir)
        book = storage.add_book(write_generated_txt(root / "smoke.txt"))
        controller, window = create_app_window(data_dir=data_dir)

        def run_smoke() -> None:
            try:
                native = controller.initialize()
                if native is None:
                    raise RuntimeError(controller.run_error or "WebView2 初始化失败")
                controller._set_mode("read", "formal-entry-smoke")
                window.evaluate_js(
                    "window.notebookPrototype.openBook"
                    f"({json.dumps(book['book_id'])}); true"
                )
                deadline = time.perf_counter() + 30
                reader_state: dict[str, Any] = {}
                while time.perf_counter() < deadline:
                    reader_state = window.evaluate_js("window.notebookReader.getState()")
                    if (
                        reader_state.get("renderedBookId") == book["book_id"]
                        and not reader_state.get("rendering")
                    ):
                        break
                    time.sleep(0.05)
                text_check = window.evaluate_js(
                    "document.getElementById('readingArticle').textContent"
                    ".includes('雨落在旧城的石板路上')"
                )
                window.evaluate_js(
                    "document.getElementById('pocWorkNote').value = "
                    "'formal entry smoke'; true"
                )
                result.update(
                    {
                        "ok": bool(
                            reader_state.get("renderedBookId") == book["book_id"]
                            and int(reader_state.get("fragmentCount", 0)) > 0
                            and text_check
                        ),
                        "renderer": controller.renderer,
                        "book_id": book["book_id"],
                        "reader": reader_state,
                    }
                )
            except Exception as error:  # pragma: no cover - live GUI only
                result["error"] = str(error)
            finally:
                controller.on_closing()

        webview.start(
            func=run_smoke,
            gui="edgechromium",
            debug=False,
            private_mode=True,
        )
        restored = PreviewStorage(data_dir).snapshot()
        result["closed_with_saved_note"] = (
            restored["work_note"] == "formal entry smoke"
        )
        result["ok"] = bool(result["ok"] and result["closed_with_saved_note"])
        print("FORMAL_WEBVIEW_SMOKE=" + json.dumps(result, ensure_ascii=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
