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
    },
}


def language() -> str:
    requested = os.environ.get("NOTEBOOK_POC_LANGUAGE", "zh-CN")
    return requested if requested in _MESSAGES else "zh-CN"


def tr(key: str, **values: object) -> str:
    template = _MESSAGES[language()].get(key, key)
    return template.format(**values)


__all__ = ["language", "tr"]
