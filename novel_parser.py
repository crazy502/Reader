"""Safe TXT loading and conservative line-based chapter recognition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from src.i18n import tr


class NovelLoadError(ValueError):
    """Raised when a novel cannot be read with the supported encodings."""


@dataclass(frozen=True)
class Chapter:
    index: int
    title: str
    content: str
    start_char: int
    end_char: int
    start_line: int


@dataclass(frozen=True)
class Novel:
    path: Path
    text: str
    chapters: tuple[Chapter, ...]


_CHINESE_NUMBER = "0-9０-９一二三四五六七八九十百千万零〇两壹贰叁肆伍陆柒捌玖拾佰仟萬"
_CHAPTER_LINE = re.compile(
    rf"^\s*第\s*[{_CHINESE_NUMBER}]+\s*(?:章|节|卷|回|篇)\b.*$",
    re.IGNORECASE,
)
_ENGLISH_CHAPTER_LINE = re.compile(r"^\s*chapter\s+\d+(?:\s*[:.\-—]\s*.*)?\s*$", re.IGNORECASE)
_MAX_TITLE_LENGTH = 60


def read_txt(path: str | Path) -> str:
    """Read a local TXT using the documented encoding fallback order."""
    source = Path(path)
    if not source.is_file():
        raise NovelLoadError(f"File not found: {source}")

    raw = source.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return raw.decode(encoding).lstrip("\ufeff")
        except UnicodeDecodeError:
            continue
    raise NovelLoadError(f"Unsupported encoding: {source}")


def is_chapter_title(line: str) -> bool:
    """Accept only short, standalone heading lines to avoid body-text matches."""
    candidate = line.strip()
    if not candidate or len(candidate) > _MAX_TITLE_LENGTH:
        return False
    return bool(_CHAPTER_LINE.fullmatch(candidate) or _ENGLISH_CHAPTER_LINE.fullmatch(candidate))


def parse_novel(path: str | Path) -> Novel:
    """Build structured chapters; unheaded files intentionally become one chapter."""
    source = Path(path)
    text = read_txt(source)
    lines = text.splitlines(keepends=True)
    headings: list[tuple[int, int, str, int]] = []
    offset = 0
    for line_number, line in enumerate(lines, start=1):
        title = line.strip()
        if is_chapter_title(title):
            headings.append((offset, offset + len(line), title, line_number))
        offset += len(line)

    if not headings:
        title = tr("body_title")
        rendered_text = f"{title}\n\n{text}"
        return Novel(
            path=source,
            text=rendered_text,
            chapters=(Chapter(0, title, text, 0, len(rendered_text), 1),),
        )

    chapters: list[Chapter] = []
    for index, (heading_start, content_start, title, start_line) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        # Keep heading offsets so the continuous reader can jump to the title.
        content = text[content_start:end].lstrip("\r\n")
        chapters.append(Chapter(index, title, content, heading_start, end, start_line))
    return Novel(path=source, text=text, chapters=tuple(chapters))
