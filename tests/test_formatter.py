"""Tests for output formatters — MarkdownFormatter and JsonFormatter."""

from __future__ import annotations

import json

import pytest

from ocr_pipeline.formatter import (
    JsonFormatter,
    MarkdownFormatter,
    YamlFrontmatterFormatter,
    get_formatter,
)
from ocr_pipeline.models import Block, EngineOutput, MetadataResult, PageResult, PageStatus


class TestMarkdownFormatter:
    def test_format_returns_merged_markdown(self):
        fmt = MarkdownFormatter()
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            merged_markdown="## Hello World",
        )
        assert fmt.format(page) == "## Hello World"

    def test_format_empty_markdown(self):
        fmt = MarkdownFormatter()
        page = PageResult(sha256="abc", page_index=1, page_label="page_0002")
        assert fmt.format(page) == ""

    def test_extension(self):
        fmt = MarkdownFormatter()
        assert fmt.extension() == ".md"


class TestJsonFormatter:
    def test_format_produces_valid_json(self):
        fmt = JsonFormatter()
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            merged_markdown="# Title\n\nContent",
            status=PageStatus.COMPLETE,
        )
        output = fmt.format(page)
        data = json.loads(output)
        assert data["page_index"] == 0
        assert data["page_label"] == "page_0001"
        assert data["markdown"] == "# Title\n\nContent"
        assert data["status"] == "complete"

    def test_format_includes_engine_outputs(self):
        fmt = JsonFormatter()
        eo = EngineOutput(engine="marker", text="some text")
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            engine_outputs={"marker": eo},
        )
        output = fmt.format(page)
        data = json.loads(output)
        assert "marker" in data["engine_outputs"]
        assert data["engine_outputs"]["marker"]["text"] == "some text"

    def test_format_includes_blocks_when_present(self):
        fmt = JsonFormatter()
        block = Block(type="heading", text="Chapter 1", confidence=0.95)
        eo = EngineOutput(engine="marker", text="text", blocks=[block])
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            engine_outputs={"marker": eo},
        )
        output = fmt.format(page)
        data = json.loads(output)
        blocks = data["engine_outputs"]["marker"]["blocks"]
        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading"

    def test_format_excludes_blocks_when_none(self):
        fmt = JsonFormatter()
        eo = EngineOutput(engine="surya2", text="plain")
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            engine_outputs={"surya2": eo},
        )
        output = fmt.format(page)
        data = json.loads(output)
        assert "blocks" not in data["engine_outputs"]["surya2"]

    def test_format_engine_output_with_error(self):
        fmt = JsonFormatter()
        eo = EngineOutput(engine="mathpix", error="timeout")
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            engine_outputs={"mathpix": eo},
        )
        output = fmt.format(page)
        data = json.loads(output)
        assert data["engine_outputs"]["mathpix"]["error"] == "timeout"

    def test_extension(self):
        fmt = JsonFormatter()
        assert fmt.extension() == ".json"


class TestGetFormatter:
    def test_markdown(self):
        fmt = get_formatter("markdown")
        assert isinstance(fmt, MarkdownFormatter)

    def test_json(self):
        fmt = get_formatter("json")
        assert isinstance(fmt, JsonFormatter)

    def test_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown output format"):
            get_formatter("xml")


# ---------------------------------------------------------------------------
# YamlFrontmatterFormatter
# ---------------------------------------------------------------------------


class TestYamlFrontmatterFormatter:
    """Tests for per-PDF concatenated markdown with YAML frontmatter."""

    def test_format_with_full_metadata(self) -> None:
        fmt = YamlFrontmatterFormatter()
        metadata = MetadataResult(
            title="Test Paper",
            authors=["Author One", "Author Two"],
            doi="10.1234/test",
            journal="Test Journal",
            volume="42",
            issue="3",
            year="2025",
            abstract="This is a test abstract.",
            keywords=["test", "paper"],
        )
        pages = [
            PageResult(
                sha256="abc",
                page_index=0,
                page_label="page_0001",
                merged_markdown="# Page 1\nContent",
            ),
            PageResult(
                sha256="abc",
                page_index=1,
                page_label="page_0002",
                merged_markdown="# Page 2\nMore",
            ),
        ]

        output = fmt.format(metadata, pages)

        # Frontmatter delimiters
        assert output.startswith("---\n")
        assert "\n---\n\n" in output

        # Metadata fields
        assert "title: Test Paper" in output
        assert "doi: 10.1234/test" in output
        assert "journal: Test Journal" in output
        assert "authors:" in output
        assert "- Author One" in output
        assert "- Author Two" in output
        assert "abstract: This is a test abstract." in output
        assert "keywords:" in output

        # Page content after frontmatter
        assert "# Page 1\nContent" in output
        assert "# Page 2\nMore" in output

    def test_format_with_none_metadata_produces_empty_frontmatter(self) -> None:
        fmt = YamlFrontmatterFormatter()
        pages = [
            PageResult(
                sha256="abc",
                page_index=0,
                page_label="page_0001",
                merged_markdown="# Only page",
            ),
        ]
        output = fmt.format(None, pages)
        # Empty frontmatter block is still valid YAML
        assert output.startswith("---\n")
        assert "{}\n" in output or output.startswith("---\n{}")
        assert "# Only page" in output

    def test_format_skips_whitespace_only_pages(self) -> None:
        fmt = YamlFrontmatterFormatter()
        pages = [
            PageResult(
                sha256="abc",
                page_index=0,
                page_label="page_0001",
                merged_markdown="  ",  # whitespace only
            ),
            PageResult(
                sha256="abc",
                page_index=1,
                page_label="page_0002",
                merged_markdown="# Real content",
            ),
        ]
        output = fmt.format(None, pages)
        # Whitespace-only page should not appear
        assert "# Real content" in output
        # The output should not have an empty paragraph from the blank page
        lines = output.split("\n")
        assert "  " not in lines

    def test_format_empty_frontmatter_with_none_metadata(self) -> None:
        """When metadata is None and no fields set, frontmatter is '{}'."""
        fmt = YamlFrontmatterFormatter()
        pages = [
            PageResult(
                sha256="abc",
                page_index=0,
                page_label="page_0001",
                merged_markdown="Some text",
            ),
        ]
        output = fmt.format(None, pages)
        # Should contain valid YAML frontmatter with empty mapping
        frontmatter_end = output.index("---\n", 4)  # skip first ---
        frontmatter_block = output[4:frontmatter_end]
        assert frontmatter_block.strip() == "{}"

    def test_extension(self) -> None:
        fmt = YamlFrontmatterFormatter()
        assert fmt.extension() == ".md"
