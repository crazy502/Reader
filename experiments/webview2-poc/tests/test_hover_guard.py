from __future__ import annotations

from pathlib import Path
import sys


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from poc import ENTER_DELAY_SECONDS, PocController  # noqa: E402


def test_pointer_enter_waits_but_pointer_exit_is_immediate() -> None:
    controller = PocController()
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


def test_dialog_guard_suppresses_hover_transitions_and_resets_enter_timer() -> None:
    controller = PocController()
    controller.hover_reading_enabled = True
    controller.app_mode = "work"

    with controller.dialog_guard():
        assert controller._process_pointer_sample(True, 20.0) is None
        assert controller._inside_since is None

    # The short post-dialog guard rejects the closing event rather than
    # interpreting it as a user hover gesture.
    guarded_time = controller._dialog_guard_until - 0.01
    assert controller._process_pointer_sample(False, guarded_time) is None
    assert controller._inside_since is None
