from __future__ import annotations

from pathlib import Path
import sys


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = EXPERIMENT_ROOT.parents[1]
for path in (EXPERIMENT_ROOT, PROJECT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from novel_engine import (  # noqa: E402
    ExperimentLibrary,
    build_chunked_fragments,
    build_whole_fragments,
    generate_synthetic_text,
)
from reader.core.novel_parser import Chapter, Novel  # noqa: E402
from reader.loaders import load_novel  # noqa: E402
from sample_data import SAMPLE_CHAPTERS, write_generated_epub, write_generated_txt  # noqa: E402


def _unicode_novel(tmp_path: Path) -> Novel:
    text = "序言 🙂\r\n第一章 开始\r\n　　中文 𝄞 与空格。\r\n\r\n第二章 继续\n正文。"
    first = text.index("第一章")
    second = text.index("第二章")
    return Novel(
        path=tmp_path / "unicode.txt",
        text=text,
        chapters=(
            Chapter(0, "第一章 开始", "　　中文 𝄞 与空格。", first, second, 2),
            Chapter(1, "第二章 继续", "正文。", second, len(text), 5),
        ),
    )


def test_both_render_strategies_preserve_exact_novel_text(tmp_path: Path) -> None:
    novel = _unicode_novel(tmp_path)

    for fragments in (build_whole_fragments(novel), build_chunked_fragments(novel)):
        assert fragments[0].start == 0
        assert fragments[-1].end == len(novel.text)
        assert "".join(fragment.text for fragment in fragments) == novel.text
        assert all(left.end == right.start for left, right in zip(fragments, fragments[1:]))


def test_chunked_strategy_uses_fewer_nodes_than_whole_book_baseline(tmp_path: Path) -> None:
    source = tmp_path / "large.txt"
    source.write_text(generate_synthetic_text(500_000), encoding="utf-8", newline="")
    novel = load_novel(source)

    whole = build_whole_fragments(novel)
    chunked = build_chunked_fragments(novel)

    assert len(whole) > len(chunked) * 10
    assert len(chunked) <= len(novel.chapters) * 3


def test_generated_txt_and_epub_use_formal_loader_and_keep_spine_order(
    tmp_path: Path,
) -> None:
    txt = load_novel(write_generated_txt(tmp_path / "sample.txt"))
    epub = load_novel(write_generated_epub(tmp_path / "sample.epub"))

    expected_titles = [title for title, _body in SAMPLE_CHAPTERS]
    assert [chapter.title for chapter in txt.chapters] == expected_titles
    assert [chapter.title for chapter in epub.chapters] == expected_titles
    assert "🙂" in txt.text and "𝄞" in txt.text
    assert "🙂" in epub.text and "𝄞" in epub.text
    assert "不应进入正文" not in epub.text
    assert epub.text.index(expected_titles[0]) < epub.text.index(expected_titles[-1])


def test_experiment_library_keeps_two_book_positions_independent(tmp_path: Path) -> None:
    first_path = write_generated_txt(tmp_path / "a.txt")
    second_path = tmp_path / "b.txt"
    second_path.write_text(generate_synthetic_text(80_000), encoding="utf-8", newline="")
    library = ExperimentLibrary()
    first = library.open_path(first_path)
    second = library.open_path(second_path)

    library.save_position(first["book_id"], 17)
    library.save_position(second["book_id"], 35_001)

    assert library.metadata(first["book_id"])["char_position"] == 17
    assert library.metadata(second["book_id"])["char_position"] == 35_001
    assert first["book_id"] != second["book_id"]


def test_payload_positions_are_python_code_point_offsets(tmp_path: Path) -> None:
    novel = _unicode_novel(tmp_path)
    library = ExperimentLibrary()
    metadata = library.register_novel(
        novel,
        book_id="unicode-boundaries",
        display_title="Unicode boundaries",
    )

    payload = library.render_payload(metadata["book_id"], "chunked")
    emoji_position = novel.text.index("🙂")
    music_position = novel.text.index("𝄞")

    assert payload["text_length"] == len(novel.text)
    assert emoji_position + 1 == novel.text.index("\r", emoji_position)
    assert music_position + 1 == novel.text.index(" ", music_position)
    assert sum(len(fragment["text"]) for fragment in payload["fragments"]) == len(
        novel.text
    )


def test_synthetic_generator_is_chaptered_and_close_to_requested_size() -> None:
    text = generate_synthetic_text(1_000_000)

    assert len(text) == 1_000_000
    assert text.startswith("第1章")
    assert text.count("\n\n") > 1_000
    assert "🙂" in text and "𝄞" in text
