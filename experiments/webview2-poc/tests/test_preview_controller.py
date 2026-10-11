from __future__ import annotations

from pathlib import Path
import sys


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from poc import PocController
from preview_storage import PreviewStorage


def _write_book(path: Path, label: str) -> Path:
    path.write_text(
        f"第一章 {label}\n\n这是第一章正文。\n\n第二章 继续\n\n这是第二章正文。",
        encoding="utf-8",
    )
    return path


def test_prepare_does_not_activate_until_complete_build_is_committed(
    tmp_path: Path,
) -> None:
    controller = PocController(
        preview_mode=True, preview_data_dir=tmp_path / "preview"
    )
    assert controller._preview is not None
    record = controller._preview.add_book(_write_book(tmp_path / "one.txt", "甲"))

    metadata = controller.prepare_preview_book(record["book_id"])
    payload = controller.render_payload(record["book_id"], "chunked")

    assert controller._preview.state.active_book_id is None
    assert metadata["book_id"] == record["book_id"]
    assert payload["book_id"] == record["book_id"]
    assert payload["text_length"] > 0

    committed = controller.commit_preview_book(record["book_id"])

    assert committed["book_id"] == record["book_id"]
    assert controller._preview.state.active_book_id == record["book_id"]


def test_two_preview_books_keep_independent_positions_after_restart(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "preview"
    controller = PocController(preview_mode=True, preview_data_dir=data_dir)
    assert controller._preview is not None
    first = controller._preview.add_book(_write_book(tmp_path / "a.txt", "甲"))
    second = controller._preview.add_book(_write_book(tmp_path / "b.txt", "乙"))

    for record, position in ((first, 11), (second, 29)):
        controller.prepare_preview_book(record["book_id"])
        controller.commit_preview_book(record["book_id"])
        controller.save_position(record["book_id"], position)

    restored = PreviewStorage(data_dir)

    assert restored.record(first["book_id"]).char_position == 11
    assert restored.record(second["book_id"]).char_position == 29
    assert restored.state.active_book_id == second["book_id"]
