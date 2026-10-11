"""Generate disposable TXT/EPUB fixtures for the isolated Phase 2 experiment."""

from __future__ import annotations

from html import escape
from pathlib import Path
from zipfile import ZIP_STORED, ZIP_DEFLATED, ZipFile


SAMPLE_CHAPTERS = (
    (
        "第一章 夜雨",
        "　　雨落在旧城的石板路上。普通中文、空格与换行都要保留。\n"
        "第二段带有 Emoji 🙂 和非 BMP 音乐符号 𝄞。",
    ),
    (
        "第二章 远行",
        "列车穿过清晨的薄雾，窗外的河流向东延伸。\n"
        "这是一段用于验证章节顺序与连续滚动的正文。",
    ),
    (
        "第三章 归来",
        "多年以后，他仍能认出站台尽头的那盏灯。\n"
        "故事在这里暂时结束，但字符位置应当仍然精确。",
    ),
)


def write_generated_txt(path: Path) -> Path:
    rendered = "\n\n".join(f"{title}\n\n{body}" for title, body in SAMPLE_CHAPTERS)
    path.write_text(rendered, encoding="utf-8", newline="")
    return path


def write_generated_epub(path: Path) -> Path:
    container = """<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml" />
  </rootfiles>
</container>"""
    manifest_items = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />',
        '<item id="image" href="images/cover.png" media-type="image/png" />',
    ]
    spine_items: list[str] = []
    navigation_items: list[str] = []
    documents: dict[str, str] = {}
    # Deliberately make archive names disagree with spine order.
    filenames = ("z-last.xhtml", "m-middle.xhtml", "a-first.xhtml")
    for index, ((title, body), filename) in enumerate(zip(SAMPLE_CHAPTERS, filenames), start=1):
        identifier = f"chapter-{index}"
        manifest_items.append(
            f'<item id="{identifier}" href="text/{filename}" media-type="application/xhtml+xml" />'
        )
        spine_items.append(f'<itemref idref="{identifier}" />')
        navigation_items.append(
            f'<li><a href="text/{filename}#start">{escape(title)}</a></li>'
        )
        paragraphs = "".join(f"<p>{escape(line)}</p>" for line in body.splitlines())
        image = '<img src="../images/cover.png" alt="不应进入正文" />' if index == 2 else ""
        documents[f"OEBPS/text/{filename}"] = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{escape(title)}</title></head>
<body><h1 id="start">{escape(title)}</h1>{image}{paragraphs}</body></html>"""

    opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>生成 EPUB 样本</dc:title></metadata>
  <manifest>{''.join(manifest_items)}</manifest>
  <spine>{''.join(spine_items)}</spine>
</package>"""
    nav = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<body><nav epub:type="toc"><ol>{''.join(navigation_items)}</ol></nav></body></html>"""

    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        archive.writestr("META-INF/container.xml", container, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/package.opf", opf, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/nav.xhtml", nav, compress_type=ZIP_DEFLATED)
        archive.writestr("OEBPS/images/cover.png", b"generated-image-placeholder")
        for name, content in documents.items():
            archive.writestr(name, content, compress_type=ZIP_DEFLATED)
    return path


__all__ = ["SAMPLE_CHAPTERS", "write_generated_epub", "write_generated_txt"]
