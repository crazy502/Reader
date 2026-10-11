"""Tiny bilingual catalogue for Python-originated PoC messages."""

from __future__ import annotations

import os


_MESSAGES = {
    "zh-CN": {
        "only_txt_epub": "仅支持 TXT 和 EPUB 文件。",
        "file_not_found": "找不到小说文件：{path}",
        "load_failed": "无法读取小说：{name}",
        "empty_novel": "小说没有可阅读的正文。",
        "unknown_strategy": "未知渲染策略：{strategy}",
        "book_not_loaded": "实验会话中找不到这本书，请重新打开。",
        "dialog_title": "选择 TXT 或 EPUB 小说",
        "dialog_file_type": "小说文件 (*.txt;*.epub)",
        "dialog_cancelled": "已取消选择文件。",
        "dialog_opened": "已载入《{title}》。",
        "invalid_benchmark_sizes": "--benchmark-sizes 必须是逗号分隔的整数。",
        "phase2_smoke_help": "用较小合成小说运行真实正文、定位和 A/B 状态冒烟检查",
        "benchmark_help": "运行 50万/100万/300万字的实际 WebView2 A/B 基准",
        "benchmark_runs_help": "每个规模/策略的重复次数（默认 3，报告中使用中位数）",
        "benchmark_sizes_help": "逗号分隔的字符规模，仅与 --benchmark 一起使用",
        "preview_appdata_required": "找不到 Windows APPDATA，无法创建测试版数据目录。",
        "preview_file_missing": "找不到所选书籍文件。",
        "preview_unsupported_file": "测试版仅支持 TXT 和 EPUB 文件。",
        "preview_book_not_found": "书架中找不到这本书。",
        "preview_invalid_title": "显示书名不能为空。",
        "preview_duplicate_relocation": "这个文件已经属于书架中的另一本书。",
        "preview_format_mismatch": "重新定位的文件格式必须与原书一致。",
        "preview_relocation_failed": "无法重新定位书籍文件。",
        "preview_note_save_failed": "无法保存工作便笺。",
        "preview_bookshelf_save_failed": "无法保存测试版书架。",
        "preview_settings_save_failed": "无法保存测试版阅读设置。",
        "default_work_note": "今日待处理\n\n",
        "hover_enabled": "悬停阅读已启用；进入窗口约 400ms 后显示阅读区域。",
        "hover_disabled": "Alt+Q：已禁用悬停阅读并返回工作模式。",
        "preview_runtime_missing": "Notebook Web Preview 需要 Microsoft Edge WebView2 Runtime。请安装后重试。",
        "preview_runtime_title": "Notebook Web Preview 无法启动",
        "preview_title": "Notebook Web Preview",
        "preview_relocate_type": "{format} 文件 (*.{extension})",
    },
    "en-US": {
        "only_txt_epub": "Only TXT and EPUB files are supported.",
        "file_not_found": "Novel file not found: {path}",
        "load_failed": "Could not load novel: {name}",
        "empty_novel": "The novel has no readable text.",
        "unknown_strategy": "Unknown rendering strategy: {strategy}",
        "book_not_loaded": "This book is not loaded in the experiment session.",
        "dialog_title": "Choose a TXT or EPUB novel",
        "dialog_file_type": "Novel files (*.txt;*.epub)",
        "dialog_cancelled": "File selection cancelled.",
        "dialog_opened": "Loaded “{title}”.",
        "invalid_benchmark_sizes": "--benchmark-sizes must be comma-separated integers.",
        "phase2_smoke_help": "Run the real-text, position, and A/B smoke test on a small synthetic novel",
        "benchmark_help": "Run the 500k/1m/3m character WebView2 A/B benchmark",
        "benchmark_runs_help": "Runs per size/strategy (default 3; reports use medians)",
        "benchmark_sizes_help": "Comma-separated character sizes used with --benchmark",
        "preview_appdata_required": "Windows APPDATA is unavailable; the preview data directory cannot be created.",
        "preview_file_missing": "The selected book file could not be found.",
        "preview_unsupported_file": "The preview supports TXT and EPUB files only.",
        "preview_book_not_found": "This book is not present on the preview shelf.",
        "preview_invalid_title": "The display title cannot be empty.",
        "preview_duplicate_relocation": "That file already belongs to another shelf entry.",
        "preview_format_mismatch": "The relocated file must use the same format as the original.",
        "preview_relocation_failed": "The book file could not be relocated.",
        "preview_note_save_failed": "The work note could not be saved.",
        "preview_bookshelf_save_failed": "The preview bookshelf could not be saved.",
        "preview_settings_save_failed": "The preview reading settings could not be saved.",
        "default_work_note": "Today's tasks\n\n",
        "hover_enabled": "Hover reading is enabled; reading appears about 400ms after entering the window.",
        "hover_disabled": "Alt+Q: hover reading disabled and work mode restored.",
        "preview_runtime_missing": "Notebook Web Preview requires Microsoft Edge WebView2 Runtime. Install it and try again.",
        "preview_runtime_title": "Notebook Web Preview could not start",
        "preview_title": "Notebook Web Preview",
        "preview_relocate_type": "{format} files (*.{extension})",
    },
}


def language() -> str:
    requested = os.environ.get("NOTEBOOK_POC_LANGUAGE", "zh-CN")
    return requested if requested in _MESSAGES else "zh-CN"


def tr(key: str, **values: object) -> str:
    template = _MESSAGES[language()].get(key, key)
    return template.format(**values)


__all__ = ["language", "tr"]
