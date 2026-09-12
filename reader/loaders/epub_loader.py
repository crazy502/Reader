"""Read reflowable EPUB 2/3 books into the shared continuous-text model."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import codecs
import posixpath
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

from ..core.novel_parser import Chapter, Novel, NovelLoadError
from ..i18n import tr


_CONTAINER_PATH = "META-INF/container.xml"
_EPUB_MIMETYPE = b"application/epub+zip"
_OPS_NAMESPACE = "http://www.idpf.org/2007/ops"
_DOCUMENT_MEDIA_TYPES = frozenset(("application/xhtml+xml", "text/html"))
_BLOCK_TAGS = frozenset(
    (
        "address",
        "article",
        "aside",
        "blockquote",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    )
)
_SUPPRESSED_TAGS = frozenset(("head", "noscript", "script", "style", "svg"))
_VOID_TAGS = frozenset(
    ("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr")
)
_WHITESPACE = re.compile(r"\s+")
_ENCODING_DECLARATION = re.compile(
    br"(?:encoding\s*=\s*|charset\s*=\s*)[\"']?\s*([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _ManifestItem:
    identifier: str
    path: str
    media_type: str
    properties: frozenset[str]


@dataclass(frozen=True)
class _TocEntry:
    title: str
    path: str
    fragment: str


@dataclass(frozen=True)
class _DocumentText:
    text: str
    anchors: dict[str, int]
    heading: str
    title: str


@dataclass(frozen=True)
class _Section:
    title: str
    content: str


class _PlainTextExtractor(HTMLParser):
    """Flatten one HTML document while retaining offsets for simple anchors."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._length = 0
        self._anchors: dict[str, int] = {}
        self._suppressed_depth = 0
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._first_heading = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = _local_name(tag).lower()
        if tag == "title":
            self._title_depth += 1

        if self._suppressed_depth:
            if tag not in _VOID_TAGS:
                self._suppressed_depth += 1
            return
        if tag in _SUPPRESSED_TAGS:
            self._suppressed_depth = 1
            return

        if tag in _BLOCK_TAGS:
            self._ensure_newlines(2)

        attributes = {name.lower(): value for name, value in attrs if value}
        anchor = attributes.get("id")
        if tag == "a":
            anchor = anchor or attributes.get("name")
        if anchor:
            self._anchors.setdefault(anchor, self._length)

        if tag in ("h1", "h2", "h3") and not self._first_heading and self._heading_tag is None:
            self._heading_tag = tag
            self._heading_parts.clear()
        if tag == "br":
            self._ensure_newlines(1)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = _local_name(tag).lower()
        if tag == "title" and self._title_depth:
            self._title_depth -= 1

        if self._suppressed_depth:
            if tag not in _VOID_TAGS:
                self._suppressed_depth -= 1
            return

        if self._heading_tag == tag:
            self._first_heading = _clean_inline("".join(self._heading_parts))
            self._heading_tag = None
            self._heading_parts.clear()
        if tag in _BLOCK_TAGS:
            self._ensure_newlines(2)

    def handle_data(self, data: str) -> None:
        if self._title_depth:
            self._title_parts.append(data)
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if not self._suppressed_depth:
            self._append_text(data)

    def document(self) -> _DocumentText:
        text = "".join(self._parts).rstrip()
        final_length = len(text)
        anchors = {name: min(offset, final_length) for name, offset in self._anchors.items()}
        return _DocumentText(
            text=text,
            anchors=anchors,
            heading=self._first_heading,
            title=_clean_inline("".join(self._title_parts)),
        )

    def _append_text(self, data: str) -> None:
        text = _WHITESPACE.sub(" ", data)
        if not text:
            return
        if self._length == 0 or self._last_character().isspace():
            text = text.lstrip()
        if text:
            self._parts.append(text)
            self._length += len(text)

    def _ensure_newlines(self, count: int) -> None:
        self._trim_trailing_spaces()
        if self._length == 0:
            return
        trailing = 0
        for part in reversed(self._parts):
            for character in reversed(part):
                if character != "\n":
                    needed = max(0, count - trailing)
                    if needed:
                        value = "\n" * needed
                        self._parts.append(value)
                        self._length += needed
                    return
                trailing += 1
        needed = max(0, count - trailing)
        if needed:
            value = "\n" * needed
            self._parts.append(value)
            self._length += needed

    def _trim_trailing_spaces(self) -> None:
        while self._parts:
            part = self._parts[-1]
            trimmed = part.rstrip(" ")
            removed = len(part) - len(trimmed)
            if not removed:
                return
            self._length -= removed
            if trimmed:
                self._parts[-1] = trimmed
                return
            self._parts.pop()

    def _last_character(self) -> str:
        for part in reversed(self._parts):
            if part:
                return part[-1]
        return "\n"


def load_epub(path: str | Path) -> Novel:
    """Load an EPUB in spine order and convert it to continuous plain text."""
    source = Path(path)
    if not source.is_file():
        raise NovelLoadError(f"File not found: {source}")

    try:
        with zipfile.ZipFile(source) as archive:
            mimetype = _read_optional_entry(archive, "mimetype")
            if mimetype is not None and mimetype.strip() != _EPUB_MIMETYPE:
                raise NovelLoadError(f"Invalid EPUB mimetype: {source}")

            opf_path = _container_rootfile(archive)
            opf_root = ET.fromstring(_read_entry(archive, opf_path))
            manifest, spine, toc_identifier = _parse_package(opf_root, opf_path)
            toc_entries = _load_toc_entries(archive, manifest, toc_identifier)
            toc_by_path = _group_toc_entries(toc_entries)

            sections: list[_Section] = []
            for identifier in spine:
                item = manifest.get(identifier)
                if item is None:
                    raise NovelLoadError(f"EPUB spine references a missing item: {identifier}")
                if not _is_document(item):
                    continue
                document = _extract_document(_read_entry(archive, item.path))
                if not document.text.strip():
                    continue
                sections.extend(
                    _sections_for_document(
                        document,
                        toc_by_path.get(item.path, ()),
                        len(sections) + 1,
                    )
                )

            if not sections:
                raise NovelLoadError(f"EPUB contains no readable text: {source}")
            return _build_novel(source, sections)
    except NovelLoadError:
        raise
    except Exception as error:
        raise NovelLoadError(f"Unable to read EPUB: {source}") from error


def _container_rootfile(archive: zipfile.ZipFile) -> str:
    root = ET.fromstring(_read_entry(archive, _CONTAINER_PATH))
    for element in root.iter():
        if _local_name(element.tag) != "rootfile":
            continue
        path = element.get("full-path", "").strip()
        normalized = _resolve_archive_path("", path)[0]
        if normalized:
            return normalized
    raise NovelLoadError("EPUB container does not declare an OPF package")


def _parse_package(
    root: ET.Element,
    opf_path: str,
) -> tuple[dict[str, _ManifestItem], tuple[str, ...], str]:
    base_path = posixpath.dirname(opf_path)
    manifest_element = _first_descendant(root, "manifest")
    spine_element = _first_descendant(root, "spine")
    if manifest_element is None or spine_element is None:
        raise NovelLoadError("EPUB package is missing its manifest or spine")

    manifest: dict[str, _ManifestItem] = {}
    for element in manifest_element:
        if _local_name(element.tag) != "item":
            continue
        identifier = element.get("id", "").strip()
        href = element.get("href", "").strip()
        path, _fragment = _resolve_archive_path(base_path, href)
        if not identifier or not path:
            continue
        manifest[identifier] = _ManifestItem(
            identifier=identifier,
            path=path,
            media_type=element.get("media-type", "").strip().lower(),
            properties=frozenset(element.get("properties", "").lower().split()),
        )

    spine: list[str] = []
    for element in spine_element:
        if _local_name(element.tag) != "itemref":
            continue
        if element.get("linear", "yes").strip().lower() == "no":
            continue
        identifier = element.get("idref", "").strip()
        if identifier:
            spine.append(identifier)
    if not spine:
        raise NovelLoadError("EPUB package has no linear reading order")
    return manifest, tuple(spine), spine_element.get("toc", "").strip()


def _load_toc_entries(
    archive: zipfile.ZipFile,
    manifest: dict[str, _ManifestItem],
    toc_identifier: str,
) -> tuple[_TocEntry, ...]:
    nav_items = [item for item in manifest.values() if "nav" in item.properties]
    for item in nav_items:
        try:
            entries = _parse_epub3_nav(_read_entry(archive, item.path), item.path)
        except (NovelLoadError, ET.ParseError):
            continue
        if entries:
            return entries

    ncx_item = manifest.get(toc_identifier)
    if ncx_item is None:
        ncx_item = next(
            (item for item in manifest.values() if item.media_type == "application/x-dtbncx+xml"),
            None,
        )
    if ncx_item is not None:
        try:
            return _parse_epub2_ncx(_read_entry(archive, ncx_item.path), ncx_item.path)
        except (NovelLoadError, ET.ParseError):
            pass
    return ()


def _parse_epub2_ncx(data: bytes, ncx_path: str) -> tuple[_TocEntry, ...]:
    root = ET.fromstring(data)
    base_path = posixpath.dirname(ncx_path)
    entries: list[_TocEntry] = []
    for nav_point in root.iter():
        if _local_name(nav_point.tag) != "navPoint":
            continue
        label = _first_descendant(nav_point, "navLabel")
        content = _first_descendant(nav_point, "content")
        title = _element_text(label)
        href = content.get("src", "") if content is not None else ""
        path, fragment = _resolve_archive_path(base_path, href)
        if title and path:
            entries.append(_TocEntry(title, path, fragment))
    return tuple(entries)


def _parse_epub3_nav(data: bytes, nav_path: str) -> tuple[_TocEntry, ...]:
    root = ET.fromstring(data)
    base_path = posixpath.dirname(nav_path)
    toc_navigation: ET.Element | None = None
    for element in root.iter():
        if _local_name(element.tag) != "nav":
            continue
        navigation_type = element.get(f"{{{_OPS_NAMESPACE}}}type", element.get("type", ""))
        if "toc" in navigation_type.lower().split():
            toc_navigation = element
            break
    if toc_navigation is None:
        return ()

    entries: list[_TocEntry] = []
    for element in toc_navigation.iter():
        if _local_name(element.tag) != "a":
            continue
        title = _element_text(element)
        path, fragment = _resolve_archive_path(base_path, element.get("href", ""))
        if title and path:
            entries.append(_TocEntry(title, path, fragment))
    return tuple(entries)


def _extract_document(data: bytes) -> _DocumentText:
    parser = _PlainTextExtractor()
    parser.feed(_decode_html(data))
    parser.close()
    return parser.document()


def _decode_html(data: bytes) -> str:
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16")

    declaration = _ENCODING_DECLARATION.search(data[:2048])
    candidates = [declaration.group(1).decode("ascii", "ignore")] if declaration else []
    candidates.extend(("utf-8", "utf-16"))
    for encoding in candidates:
        if not encoding:
            continue
        try:
            codecs.lookup(encoding)
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _sections_for_document(
    document: _DocumentText,
    toc_entries: tuple[_TocEntry, ...],
    fallback_number: int,
) -> tuple[_Section, ...]:
    fragment_entries = tuple(entry for entry in toc_entries if entry.fragment)
    if len(toc_entries) > 1 and len(fragment_entries) == len(toc_entries):
        positions = [document.anchors.get(entry.fragment) for entry in fragment_entries]
        if all(position is not None for position in positions):
            resolved = [int(position) for position in positions if position is not None]
            if all(left < right for left, right in zip(resolved, resolved[1:])):
                split_sections: list[_Section] = []
                for index, entry in enumerate(fragment_entries):
                    start = 0 if index == 0 else resolved[index]
                    end = resolved[index + 1] if index + 1 < len(resolved) else len(document.text)
                    content = _without_duplicate_heading(document.text[start:end], entry.title)
                    split_sections.append(_Section(entry.title, content))
                return tuple(split_sections)

    toc_title = next((entry.title for entry in toc_entries if entry.title), "")
    title = toc_title or document.title or document.heading or _fallback_title(fallback_number)
    return (_Section(title, _without_duplicate_heading(document.text, title)),)


def _build_novel(source: Path, sections: list[_Section]) -> Novel:
    rendered_sections: list[str] = []
    starts: list[int] = []
    start_lines: list[int] = []
    text_length = 0
    line_number = 1
    for section in sections:
        if rendered_sections:
            separator = "\n\n"
            text_length += len(separator)
            line_number += separator.count("\n")
        starts.append(text_length)
        start_lines.append(line_number)
        rendered = section.title
        if section.content:
            rendered = f"{rendered}\n\n{section.content}"
        rendered_sections.append(rendered)
        text_length += len(rendered)
        line_number += rendered.count("\n")

    text = "\n\n".join(rendered_sections)
    chapters = tuple(
        Chapter(
            index=index,
            title=section.title,
            content=section.content,
            start_char=starts[index],
            end_char=starts[index + 1] if index + 1 < len(starts) else len(text),
            start_line=start_lines[index],
        )
        for index, section in enumerate(sections)
    )
    return Novel(path=source, text=text, chapters=chapters)


def _group_toc_entries(entries: tuple[_TocEntry, ...]) -> dict[str, tuple[_TocEntry, ...]]:
    grouped: dict[str, list[_TocEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.path, []).append(entry)
    return {path: tuple(path_entries) for path, path_entries in grouped.items()}


def _without_duplicate_heading(text: str, title: str) -> str:
    content = text.strip()
    if not content:
        return ""
    lines = content.splitlines()
    if lines and _clean_inline(lines[0]).casefold() == _clean_inline(title).casefold():
        return "\n".join(lines[1:]).strip()
    return content


def _fallback_title(number: int) -> str:
    return tr("epub_fallback_chapter", index=number)


def _is_document(item: _ManifestItem) -> bool:
    return item.media_type in _DOCUMENT_MEDIA_TYPES or posixpath.splitext(item.path)[1].lower() in (
        ".htm",
        ".html",
        ".xhtml",
    )


def _resolve_archive_path(base_path: str, href: str) -> tuple[str, str]:
    split = urlsplit(href.replace("\\", "/"))
    if split.scheme or split.netloc:
        return "", ""
    relative_path = unquote(split.path).lstrip("/")
    path = posixpath.normpath(posixpath.join(base_path, relative_path))
    if not relative_path or path in ("", ".", "..") or path.startswith("../"):
        return "", unquote(split.fragment)
    return path, unquote(split.fragment)


def _read_entry(archive: zipfile.ZipFile, path: str) -> bytes:
    try:
        return archive.read(path)
    except KeyError as error:
        raise NovelLoadError(f"EPUB archive is missing: {path}") from error


def _read_optional_entry(archive: zipfile.ZipFile, path: str) -> bytes | None:
    try:
        return archive.read(path)
    except KeyError:
        return None


def _first_descendant(element: ET.Element, name: str) -> ET.Element | None:
    for descendant in element.iter():
        if descendant is not element and _local_name(descendant.tag) == name:
            return descendant
    return None


def _element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return _clean_inline("".join(element.itertext()))


def _clean_inline(value: str) -> str:
    return " ".join(value.split())


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


__all__ = ["load_epub"]
