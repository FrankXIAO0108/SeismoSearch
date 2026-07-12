from pathlib import Path

from seismosearch.doc_retriever import (
    is_non_retrieval_section_heading,
    split_markdown_into_chunks,
)


def test_non_retrieval_heading_aliases() -> None:
    """元信息章节标题应被识别为非检索内容。"""
    ignored_headings = [
        "Example Queries",
        "示例问题",
        "Sources",
        "References",
        "参考资料",
        "Relation to Evaluation",
        "Evaluation Notes",
        "文档目的",
    ]

    for heading in ignored_headings:
        assert is_non_retrieval_section_heading(
            heading
        )


def test_normal_knowledge_headings_are_retained() -> None:
    """正常领域知识章节不能被误过滤。"""
    retained_headings = [
        "Magnitude",
        "Structured Magnitude Filtering",
        "Seismic Hazard",
        "Future Specific Earthquake Prediction",
        "Relation to SeismoSearch",
    ]

    for heading in retained_headings:
        assert not is_non_retrieval_section_heading(
            heading
        )


def test_split_markdown_excludes_meta_sections() -> None:
    """Markdown 切块时应跳过示例、评测和引用章节。"""
    markdown_text = """
# Test Seismology Document

Document introduction.

## Magnitude

Magnitude describes earthquake size.

## Example Queries

What does magnitude mean?

## Relation to Evaluation

This section contains evaluation-oriented examples.

## Sources

Official source list.

## Depth

Depth describes the hypocenter location.
""".strip()

    chunks = split_markdown_into_chunks(
        text=markdown_text,
        source_path=Path(
            "data/processed/docs/test_document.md"
        ),
    )

    headings = {
        chunk.heading
        for chunk in chunks
    }

    combined_text = "\n".join(
        chunk.text
        for chunk in chunks
    )

    assert "Magnitude" in headings
    assert "Depth" in headings

    assert "Example Queries" not in headings
    assert "Relation to Evaluation" not in headings
    assert "Sources" not in headings

    assert "What does magnitude mean?" not in combined_text
    assert "evaluation-oriented examples" not in combined_text
    assert "Official source list." not in combined_text