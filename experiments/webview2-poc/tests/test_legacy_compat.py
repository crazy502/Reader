from __future__ import annotations

import argparse
from pathlib import Path
import sys


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

import poc  # noqa: E402
import preview_storage  # noqa: E402
from reader.webview.storage import PreviewStorage  # noqa: E402


def test_legacy_storage_is_a_direct_formal_export() -> None:
    assert preview_storage.PreviewStorage is PreviewStorage


def test_legacy_preview_without_experiment_flags_routes_to_formal_entry(
    monkeypatch,
) -> None:
    args = argparse.Namespace(
        smoke_test=False,
        phase2_smoke=False,
        preview_smoke=False,
        benchmark=False,
        benchmark_runs=3,
        benchmark_sizes="500000",
        debug=True,
    )
    received: list[list[str]] = []
    monkeypatch.setattr(poc, "parse_args", lambda: args)
    monkeypatch.setattr(
        poc,
        "webview_main",
        lambda argv: received.append(argv) or 17,
    )

    assert poc.main(preview_mode=True) == 17
    assert received == [["--debug"]]
