"""Small message catalog used by the Tkinter UI."""

from .zh_CN import MESSAGES


def tr(key: str, **values: object) -> str:
    """Return a localized user-facing string."""
    return MESSAGES[key].format(**values)
