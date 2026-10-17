"""Compatibility exports for the historical WebView2 Preview tests."""

from reader.webview.storage import (
    DEFAULT_THEME,
    PREVIEW_APP_NAME,
    PreviewStorage,
    PreviewStorageError,
    resolve_preview_data_dir,
)


__all__ = [
    "DEFAULT_THEME",
    "PREVIEW_APP_NAME",
    "PreviewStorage",
    "PreviewStorageError",
    "resolve_preview_data_dir",
]
