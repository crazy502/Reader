from __future__ import annotations

from pathlib import Path

from reader.core.work_note import load_work_note, save_work_note


def test_missing_work_note_uses_default_template(tmp_path: Path) -> None:
    target = tmp_path / "work_note.txt"

    assert load_work_note(target, "今日待处理\n\n备注：\n") == "今日待处理\n\n备注：\n"


def test_utf8_work_note_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "work_note.txt"
    content = "今日待处理\n数据核对\n备注：下午完成\n"

    assert save_work_note(target, content)
    assert target.read_bytes() == content.encode("utf-8")
    assert load_work_note(target, "默认") == content


def test_empty_work_note_can_be_saved(tmp_path: Path) -> None:
    target = tmp_path / "work_note.txt"

    assert save_work_note(target, "")
    assert load_work_note(target, "默认") == ""


def test_atomic_save_leaves_no_temporary_file(tmp_path: Path) -> None:
    target = tmp_path / "work_note.txt"

    assert save_work_note(target, "内容")
    assert target.read_text(encoding="utf-8") == "内容"
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_replace_preserves_existing_note_and_cleans_temp(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "work_note.txt"
    target.write_text("原内容", encoding="utf-8")

    def failed_replace(_source: Path, _destination: Path) -> Path:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", failed_replace)

    assert not save_work_note(target, "新内容")
    assert target.read_text(encoding="utf-8") == "原内容"
    assert not list(tmp_path.glob("*.tmp"))
