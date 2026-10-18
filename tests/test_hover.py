from __future__ import annotations

from reader.webview.controller import ENTER_DELAY_SECONDS, WebViewController


def test_pointer_enter_waits_but_pointer_exit_is_immediate(tmp_path) -> None:
    controller = WebViewController(data_dir=tmp_path / "data")
    controller.hover_reading_enabled = True
    controller.app_mode = "work"

    assert controller._process_pointer_sample(True, 10.0) is None
    assert controller._process_pointer_sample(
        True, 10.0 + ENTER_DELAY_SECONDS - 0.01
    ) is None
    assert controller._process_pointer_sample(
        True, 10.0 + ENTER_DELAY_SECONDS
    ) == "read"

    controller.app_mode = "read"
    assert controller._process_pointer_sample(False, 11.0) == "work"


def test_dialog_guard_suppresses_hover_transition(tmp_path) -> None:
    controller = WebViewController(data_dir=tmp_path / "data")
    controller.hover_reading_enabled = True
    controller.app_mode = "work"

    with controller.dialog_guard():
        assert controller._process_pointer_sample(True, 20.0) is None
        assert controller._inside_since is None

    guarded_time = controller._dialog_guard_until - 0.01
    assert controller._process_pointer_sample(False, guarded_time) is None
    assert controller._inside_since is None
