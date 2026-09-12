"""Load supported novel formats into the shared continuous-reading model."""

from __future__ import annotations

from pathlib import Path

from ..core.novel_parser import Novel, NovelLoadError, parse_novel
from .epub_loader import load_epub


def load_novel(path: str | Path) -> Novel:
    """Dispatch a local novel to the loader selected by its file extension."""
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".txt":
        return parse_novel(source)
    if suffix == ".epub":
        return load_epub(source)
    raise NovelLoadError(f"Unsupported file type: {source.suffix or '<none>'}")


__all__ = ["load_epub", "load_novel"]
