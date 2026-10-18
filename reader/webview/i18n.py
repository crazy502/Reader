"""Bilingual catalogue for Python-originated WebView2 messages."""

from __future__ import annotations

import os


_MESSAGES = {
    "zh-CN": {
        "only_txt_epub": "仅支持 TXT 和 EPUB 文件。",
        "file_not_found": "找不到小说文件：{path}",
        "load_failed": "无法读取小说：{name}",
        "empty_novel": "小说没有可阅读的正文。",
        "book_not_loaded": "当前会话中找不到这本书，请重新打开。",
        "dialog_title": "选择 TXT 或 EPUB 小说",
        "dialog_file_type": "小说文件 (*.txt;*.epub)",
        "dialog_cancelled": "已取消选择文件。",
        "dialog_opened": "已载入《{title}》。",
        "appdata_required": "找不到 Windows APPDATA，无法创建 Notebook 数据目录。",
        "file_missing": "找不到所选书籍文件。",
        "unsupported_file": "仅支持 TXT 和 EPUB 文件。",
        "book_not_found": "书架中找不到这本书。",
        "invalid_title": "显示书名不能为空。",
        "duplicate_relocation": "这个文件已经属于书架中的另一本书。",
        "format_mismatch": "重新定位的文件格式必须与原书一致。",
        "relocation_failed": "无法重新定位书籍文件。",
        "note_save_failed": "无法保存工作便笺。",
        "bookshelf_save_failed": "无法保存书架。",
        "settings_save_failed": "无法保存阅读设置。",
        "default_work_note": "今日待处理\n\n",
        "hover_enabled": "悬停阅读已启用；进入窗口约 400ms 后显示阅读区域。",
        "hover_disabled": "Alt+Q：已禁用悬停阅读并返回工作模式。",
        "runtime_missing": "Notebook 需要 Microsoft Edge WebView2 Runtime。请安装后重试。",
        "runtime_title": "Notebook 无法启动",
        "app_title": "Notebook",
        "relocate_type": "{format} 文件 (*.{extension})",
    },
    "en-US": {
        "only_txt_epub": "Only TXT and EPUB files are supported.",
        "file_not_found": "Novel file not found: {path}",
        "load_failed": "Could not load novel: {name}",
        "empty_novel": "The novel has no readable text.",
        "book_not_loaded": "This book is not loaded in the current session.",
        "dialog_title": "Choose a TXT or EPUB novel",
        "dialog_file_type": "Novel files (*.txt;*.epub)",
        "dialog_cancelled": "File selection cancelled.",
        "dialog_opened": "Loaded “{title}”.",
        "appdata_required": "Windows APPDATA is unavailable; the Notebook data directory cannot be created.",
        "file_missing": "The selected book file could not be found.",
        "unsupported_file": "Only TXT and EPUB files are supported.",
        "book_not_found": "This book is not present on the shelf.",
        "invalid_title": "The display title cannot be empty.",
        "duplicate_relocation": "That file already belongs to another shelf entry.",
        "format_mismatch": "The relocated file must use the same format as the original.",
        "relocation_failed": "The book file could not be relocated.",
        "note_save_failed": "The work note could not be saved.",
        "bookshelf_save_failed": "The bookshelf could not be saved.",
        "settings_save_failed": "The reading settings could not be saved.",
        "default_work_note": "Today's tasks\n\n",
        "hover_enabled": "Hover reading is enabled; reading appears about 400ms after entering the window.",
        "hover_disabled": "Alt+Q: hover reading disabled and work mode restored.",
        "runtime_missing": "Notebook requires Microsoft Edge WebView2 Runtime. Install it and try again.",
        "runtime_title": "Notebook could not start",
        "app_title": "Notebook",
        "relocate_type": "{format} files (*.{extension})",
    },
}


def language() -> str:
    requested = os.environ.get("NOTEBOOK_LANGUAGE", "zh-CN")
    return requested if requested in _MESSAGES else "zh-CN"


def tr(key: str, **values: object) -> str:
    template = _MESSAGES[language()].get(key, key)
    return template.format(**values)


__all__ = ["language", "tr"]
