"""Windows virtual-environment compatibility for Tcl/Tk discovery."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def configure() -> None:
    """Point Tkinter at the base Python Tcl/Tk folders when needed."""
    base = Path(sys.base_prefix)
    tcl_dir = base / "tcl" / "tcl8.6"
    tk_dir = base / "tcl" / "tk8.6"
    if (tcl_dir / "init.tcl").is_file():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
    if (tk_dir / "tk.tcl").is_file():
        os.environ.setdefault("TK_LIBRARY", str(tk_dir))
