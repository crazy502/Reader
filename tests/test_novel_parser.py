from __future__ import annotations

from pathlib import Path

import pytest

from reader.core.novel_parser import is_chapter_title, parse_novel, read_txt


@pytest.mark.parametrize(
    ("encoding", "content"),
    [
        ("utf-8", "第一章 开始\nUTF-8 正文"),
        ("utf-8-sig", "第一章 开始\n带签名正文"),
        ("gbk", "第一章 开始\n简体中文正文"),
        ("gb18030", "Chapter 1: Start\n扩展字符𠀀"),
    ],
)
def test_supported_txt_encodings(tmp_path: Path, encoding: str, content: str) -> None:
    source = tmp_path / f"novel-{encoding}.txt"
    source.write_bytes(content.encode(encoding))

    assert read_txt(source) == content


@pytest.mark.parametrize(
    "title",
    ["第一章 开始", "第2章 后续", "第一节 序幕", "第十回 重逢", "第一卷 新世界"],
)
def test_chinese_chapter_titles(title: str) -> None:
    assert is_chapter_title(title)


@pytest.mark.parametrize(
    "title",
    ["Chapter 1", "Chapter 2: Continue", "chapter 3 - ending"],
)
def test_english_chapter_titles(title: str) -> None:
    assert is_chapter_title(title)


def test_unheaded_txt_becomes_one_continuous_body(tmp_path: Path) -> None:
    source = tmp_path / "plain.txt"
    source.write_bytes("没有章节标题\n只有正文".encode("utf-8"))

    novel = parse_novel(source)

    assert len(novel.chapters) == 1
    assert novel.chapters[0].start_char == 0
    assert novel.chapters[0].content == "没有章节标题\n只有正文"
    assert novel.text.endswith("没有章节标题\n只有正文")


def test_empty_txt_is_represented_as_an_empty_body(tmp_path: Path) -> None:
    source = tmp_path / "empty.txt"
    source.write_bytes(b"")

    novel = parse_novel(source)

    assert len(novel.chapters) == 1
    assert novel.chapters[0].content == ""
    assert novel.chapters[0].start_char == 0


def test_chapter_offsets_and_order_follow_source_text(tmp_path: Path) -> None:
    content = "第一章 开始\n第一段\n第二章 继续\n第二段\n第三章 结束\n第三段"
    source = tmp_path / "chapters.txt"
    source.write_bytes(content.encode("utf-8"))

    novel = parse_novel(source)
    starts = [chapter.start_char for chapter in novel.chapters]

    assert [chapter.index for chapter in novel.chapters] == [0, 1, 2]
    assert [chapter.title for chapter in novel.chapters] == ["第一章 开始", "第二章 继续", "第三章 结束"]
    assert starts == [content.index("第一章"), content.index("第二章"), content.index("第三章")]
    assert novel.chapters[0].end_char == starts[1]
    assert novel.chapters[1].end_char == starts[2]
    assert novel.chapters[2].end_char == len(content)


def test_many_chapters_parse_stably(tmp_path: Path) -> None:
    content = "".join(f"Chapter {index}: Title {index}\nBody {index}\n" for index in range(1, 1501))
    source = tmp_path / "many-chapters.txt"
    source.write_bytes(content.encode("utf-8"))

    first = parse_novel(source)
    second = parse_novel(source)

    assert len(first.chapters) == 1500
    assert first.chapters == second.chapters
    assert all(
        left.start_char < right.start_char
        for left, right in zip(first.chapters, first.chapters[1:])
    )
