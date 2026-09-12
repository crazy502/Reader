from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest

from reader.core.novel_parser import Novel, NovelLoadError
from reader.loaders.epub_loader import load_epub


_CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0"
 xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf"
      media-type="application/oebps-package+xml" />
  </rootfiles>
</container>
"""


def _xhtml(*, title: str = "", body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{title}</title></head>
  <body>{body}</body>
</html>
"""


def _write_epub(target: Path, entries: dict[str, str | bytes]) -> Path:
    with ZipFile(target, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        archive.writestr("META-INF/container.xml", _CONTAINER)
        for name, content in entries.items():
            archive.writestr(name, content)
    return target


def _assert_chapter_coordinates_are_exact(novel: Novel) -> None:
    assert [chapter.index for chapter in novel.chapters] == list(
        range(len(novel.chapters))
    )
    assert all(
        left.start_char < right.start_char
        for left, right in zip(novel.chapters, novel.chapters[1:])
    )

    for index, chapter in enumerate(novel.chapters):
        expected_end = (
            novel.chapters[index + 1].start_char
            if index + 1 < len(novel.chapters)
            else len(novel.text)
        )
        assert novel.text[
            chapter.start_char : chapter.start_char + len(chapter.title)
        ] == chapter.title
        assert chapter.start_char == 0 or novel.text[chapter.start_char - 1] == "\n"
        assert chapter.start_line == novel.text.count("\n", 0, chapter.start_char) + 1
        assert chapter.end_char == expected_end
        assert chapter.start_char < chapter.end_char
        assert chapter.content.strip()


def test_epub2_uses_ncx_titles_and_spine_order_not_filenames(tmp_path: Path) -> None:
    opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>测试小说</dc:title>
  </metadata>
  <manifest>
    <item id="doc-a" href="text/a.xhtml" media-type="application/xhtml+xml" />
    <item id="doc-z" href="text/z.xhtml" media-type="application/xhtml+xml" />
    <item id="cover" href="images/cover.png" media-type="image/png" />
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml" />
  </manifest>
  <spine toc="ncx">
    <itemref idref="doc-z" />
    <itemref idref="doc-a" />
  </spine>
</package>
"""
    ncx = """<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <navMap>
    <navPoint id="z" playOrder="1">
      <navLabel><text>第一章 中文开篇</text></navLabel>
      <content src="text/z.xhtml#start" />
    </navPoint>
    <navPoint id="a" playOrder="2">
      <navLabel><text>第二章 中文后续</text></navLabel>
      <content src="text/a.xhtml" />
    </navPoint>
  </navMap>
</ncx>
"""
    source = _write_epub(
        tmp_path / "spine.epub",
        {
            "OEBPS/content.opf": opf,
            "OEBPS/toc.ncx": ncx,
            "OEBPS/text/a.xhtml": _xhtml(
                title="错误的文档标题 A",
                body="<h1>错误的正文标题 A</h1><p>文件名靠前但应后读。</p>",
            ),
            "OEBPS/text/z.xhtml": _xhtml(
                title="错误的文档标题 Z",
                body=(
                    '<h1 id="start">错误的正文标题 Z</h1>'
                    '<p>图片前<img src="../images/cover.png" alt="封面替代文字" />图片后。</p>'
                    "<p>这是第一段中文正文。</p>"
                ),
            ),
            "OEBPS/images/cover.png": b"not-a-real-image-but-never-decoded",
        },
    )

    novel = load_epub(source)

    assert novel.path == source
    assert [chapter.title for chapter in novel.chapters] == [
        "第一章 中文开篇",
        "第二章 中文后续",
    ]
    assert novel.text.index("这是第一段中文正文") < novel.text.index("文件名靠前但应后读")
    assert novel.text.index("图片前") < novel.text.index("图片后")
    assert "封面替代文字" not in novel.text
    _assert_chapter_coordinates_are_exact(novel)


def test_epub3_uses_nav_titles_while_preserving_spine_order(tmp_path: Path) -> None:
    opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>EPUB 3 测试</dc:title>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />
    <item id="second" href="text/second.xhtml" media-type="application/xhtml+xml" />
    <item id="first" href="text/first.xhtml" media-type="application/xhtml+xml" />
  </manifest>
  <spine>
    <itemref idref="first" />
    <itemref idref="second" />
  </spine>
</package>
"""
    nav = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops">
  <head><title>Navigation</title></head>
  <body>
    <nav epub:type="toc">
      <ol>
        <li><a href="text/first.xhtml#chapter">导航标题一</a></li>
        <li><a href="text/second.xhtml">导航标题二</a></li>
      </ol>
    </nav>
  </body>
</html>
"""
    source = _write_epub(
        tmp_path / "navigation.epub",
        {
            "OEBPS/content.opf": opf,
            "OEBPS/nav.xhtml": nav,
            "OEBPS/text/first.xhtml": _xhtml(
                title="不应采用的 title",
                body='<h1 id="chapter">不应采用的 h1</h1><p>第一篇正文。</p>',
            ),
            "OEBPS/text/second.xhtml": _xhtml(
                title="另一个 title",
                body="<h2>另一个 h2</h2><p>第二篇正文。</p>",
            ),
        },
    )

    novel = load_epub(source)

    assert [chapter.title for chapter in novel.chapters] == ["导航标题一", "导航标题二"]
    assert novel.text.index("第一篇正文") < novel.text.index("第二篇正文")
    _assert_chapter_coordinates_are_exact(novel)


def test_simple_toc_fragments_split_one_document_in_anchor_order(tmp_path: Path) -> None:
    opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />
    <item id="body" href="body.xhtml" media-type="application/xhtml+xml" />
  </manifest>
  <spine><itemref idref="body" /></spine>
</package>
"""
    nav = """<html xmlns="http://www.w3.org/1999/xhtml"
  xmlns:epub="http://www.idpf.org/2007/ops"><body><nav epub:type="toc"><ol>
  <li><a href="body.xhtml#one">锚点章节一</a></li>
  <li><a href="body.xhtml#two">锚点章节二</a></li>
</ol></nav></body></html>"""
    source = _write_epub(
        tmp_path / "fragments.epub",
        {
            "OEBPS/content.opf": opf,
            "OEBPS/nav.xhtml": nav,
            "OEBPS/body.xhtml": _xhtml(
                body=(
                    '<h1 id="one">锚点章节一</h1><p>第一段正文。</p>'
                    '<h1 id="two">锚点章节二</h1><p>第二段正文。</p>'
                )
            ),
        },
    )

    novel = load_epub(source)

    assert [chapter.title for chapter in novel.chapters] == ["锚点章节一", "锚点章节二"]
    assert "第一段正文" in novel.chapters[0].content
    assert "第二段正文" not in novel.chapters[0].content
    assert "第二段正文" in novel.chapters[1].content
    _assert_chapter_coordinates_are_exact(novel)


def test_unreliable_fragments_fall_back_to_one_document_chapter(tmp_path: Path) -> None:
    opf = """<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />
    <item id="body" href="body.xhtml" media-type="application/xhtml+xml" />
  </manifest>
  <spine><itemref idref="body" /></spine>
</package>"""
    nav = """<html xmlns="http://www.w3.org/1999/xhtml"
  xmlns:epub="http://www.idpf.org/2007/ops"><body><nav epub:type="toc"><ol>
  <li><a href="body.xhtml#one">目录标题一</a></li>
  <li><a href="body.xhtml#missing">目录标题二</a></li>
</ol></nav></body></html>"""
    source = _write_epub(
        tmp_path / "bad-fragments.epub",
        {
            "OEBPS/content.opf": opf,
            "OEBPS/nav.xhtml": nav,
            "OEBPS/body.xhtml": _xhtml(
                title="文档标题",
                body='<h1 id="one">正文标题</h1><p>完整正文仍然保留。</p>',
            ),
        },
    )

    novel = load_epub(source)

    assert [chapter.title for chapter in novel.chapters] == ["目录标题一"]
    assert "完整正文仍然保留" in novel.chapters[0].content
    _assert_chapter_coordinates_are_exact(novel)


def test_self_closing_suppressed_markup_does_not_hide_following_text(tmp_path: Path) -> None:
    opf = """<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest><item id="body" href="body.xhtml" media-type="application/xhtml+xml" /></manifest>
  <spine><itemref idref="body" /></spine>
</package>"""
    source = _write_epub(
        tmp_path / "self-closing.epub",
        {
            "OEBPS/content.opf": opf,
            "OEBPS/body.xhtml": _xhtml(
                title="自闭合标签",
                body="<svg/><script/><style/><p>标签后的正文必须保留。</p>",
            ),
        },
    )

    novel = load_epub(source)

    assert "标签后的正文必须保留" in novel.text
    _assert_chapter_coordinates_are_exact(novel)


def test_prefixed_xhtml_tags_are_parsed_without_leaking_head_text(tmp_path: Path) -> None:
    opf = """<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest><item id="body" href="body.xhtml" media-type="application/xhtml+xml" /></manifest>
  <spine><itemref idref="body" /></spine>
</package>"""
    body = """<xhtml:html xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <xhtml:head><xhtml:title>前缀文档标题</xhtml:title></xhtml:head>
  <xhtml:body><xhtml:h1>前缀正文标题</xhtml:h1><xhtml:p>前缀正文内容。</xhtml:p></xhtml:body>
</xhtml:html>"""
    source = _write_epub(
        tmp_path / "prefixed-xhtml.epub",
        {
            "OEBPS/content.opf": opf,
            "OEBPS/body.xhtml": body,
        },
    )

    novel = load_epub(source)

    assert [chapter.title for chapter in novel.chapters] == ["前缀文档标题"]
    assert "前缀正文内容" in novel.chapters[0].content
    assert novel.chapters[0].content.count("前缀文档标题") == 0
    _assert_chapter_coordinates_are_exact(novel)


def test_title_fallback_uses_title_then_headings_then_generated_name(
    tmp_path: Path,
) -> None:
    opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Fallback</dc:title></metadata>
  <manifest>
    <item id="one" href="one.xhtml" media-type="application/xhtml+xml" />
    <item id="two" href="two.xhtml" media-type="application/xhtml+xml" />
    <item id="three" href="three.xhtml" media-type="application/xhtml+xml" />
    <item id="four" href="four.xhtml" media-type="application/xhtml+xml" />
  </manifest>
  <spine>
    <itemref idref="one" /><itemref idref="two" />
    <itemref idref="three" /><itemref idref="four" />
  </spine>
</package>
"""
    source = _write_epub(
        tmp_path / "fallback.epub",
        {
            "OEBPS/content.opf": opf,
            "OEBPS/one.xhtml": _xhtml(
                title="来自 title",
                body="<h1>不应覆盖 title</h1><p>正文一。</p>",
            ),
            "OEBPS/two.xhtml": _xhtml(
                body="<h1>来自 h1</h1><p>正文二。</p>",
            ),
            "OEBPS/three.xhtml": _xhtml(
                body="<h2>来自 h2</h2><p>正文三。</p>",
            ),
            "OEBPS/four.xhtml": _xhtml(
                body=(
                    "<style>.hidden { color: red; }</style>"
                    "<script>window.should_not_appear = true;</script>"
                    "<p>没有标题的正文。</p>"
                ),
            ),
        },
    )

    novel = load_epub(source)

    assert [chapter.title for chapter in novel.chapters] == [
        "来自 title",
        "来自 h1",
        "来自 h2",
        "第4章",
    ]
    assert ".hidden" not in novel.text
    assert "window.should_not_appear" not in novel.text
    assert "没有标题的正文" in novel.text
    _assert_chapter_coordinates_are_exact(novel)


def test_bad_zip_is_reported_as_novel_load_error(tmp_path: Path) -> None:
    source = tmp_path / "broken.epub"
    source.write_bytes(b"this is not a zip archive")

    with pytest.raises(NovelLoadError):
        load_epub(source)


@pytest.mark.parametrize("missing_part", ["container", "opf", "spine"])
def test_missing_required_epub_structure_is_reported_as_novel_load_error(
    tmp_path: Path, missing_part: str
) -> None:
    source = tmp_path / f"missing-{missing_part}.epub"
    with ZipFile(source, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        if missing_part != "container":
            archive.writestr("META-INF/container.xml", _CONTAINER)
        if missing_part == "spine":
            archive.writestr(
                "OEBPS/content.opf",
                """<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest><item id="body" href="body.xhtml" media-type="application/xhtml+xml" /></manifest>
</package>""",
            )
            archive.writestr(
                "OEBPS/body.xhtml",
                _xhtml(title="Body", body="<p>正文</p>"),
            )

    with pytest.raises(NovelLoadError):
        load_epub(source)
