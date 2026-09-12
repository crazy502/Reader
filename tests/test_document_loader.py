from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest

from reader.core.novel_parser import NovelLoadError, parse_novel
from reader.loaders import load_novel


def _write_minimal_epub(target: Path) -> Path:
    container = """<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="book.opf" media-type="application/oebps-package+xml" /></rootfiles>
</container>"""
    opf = """<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>测试</dc:title></metadata>
  <manifest><item id="body" href="body.xhtml" media-type="application/xhtml+xml" /></manifest>
  <spine><itemref idref="body" /></spine>
</package>"""
    body = """<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>EPUB 章节</title></head><body><p>EPUB 正文</p></body>
</html>"""
    with ZipFile(target, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("book.opf", opf)
        archive.writestr("body.xhtml", body)
    return target


def test_txt_dispatch_preserves_existing_parser_result(tmp_path: Path) -> None:
    source = tmp_path / "NOVEL.TXT"
    source.write_text("第一章 开始\nTXT 正文\n", encoding="utf-8")

    assert load_novel(source) == parse_novel(source)


def test_epub_dispatch_is_case_insensitive(tmp_path: Path) -> None:
    source = _write_minimal_epub(tmp_path / "NOVEL.EPUB")

    novel = load_novel(source)

    assert novel.path == source
    assert [chapter.title for chapter in novel.chapters] == ["EPUB 章节"]
    assert "EPUB 正文" in novel.text


@pytest.mark.parametrize("extension", [".mobi", ".azw3"])
def test_unsupported_ebook_formats_are_rejected(
    tmp_path: Path, extension: str
) -> None:
    source = tmp_path / f"unsupported{extension}"
    source.write_bytes(b"not a supported book")

    with pytest.raises(NovelLoadError):
        load_novel(source)
