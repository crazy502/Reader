"""Shared messages used by the novel loaders and core modules."""

from .zh_CN import MESSAGES


def tr(key: str, **values: object) -> str:
    """Return a localized user-facing string."""
    return MESSAGES[key].format(**values)
