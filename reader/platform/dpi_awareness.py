"""Windows DPI awareness setup that must run before Tk creates a window."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys


_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
_PROCESS_PER_MONITOR_DPI_AWARE = 2


def configure() -> None:
    """Enable the best available per-monitor DPI mode on Windows."""
    if sys.platform != "win32":
        return
    if _set_per_monitor_v2():
        return
    if _set_per_monitor_v1():
        return
    _set_system_aware()


def _set_per_monitor_v2() -> bool:
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        setter = user32.SetProcessDpiAwarenessContext
        setter.argtypes = [ctypes.c_void_p]
        setter.restype = wintypes.BOOL
        return bool(setter(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
    except (AttributeError, OSError):
        return False


def _set_per_monitor_v1() -> bool:
    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        setter = shcore.SetProcessDpiAwareness
        setter.argtypes = [ctypes.c_int]
        setter.restype = ctypes.c_long
        return setter(_PROCESS_PER_MONITOR_DPI_AWARE) == 0
    except (AttributeError, OSError):
        return False


def _set_system_aware() -> None:
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        setter = user32.SetProcessDPIAware
        setter.argtypes = []
        setter.restype = wintypes.BOOL
        setter()
    except (AttributeError, OSError):
        return
