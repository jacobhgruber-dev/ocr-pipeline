"""Tests for output formatters — MarkdownFormatter and JsonFormatter."""

from __future__ import annotations

import json

import pytest

import lxml.etree as ET

from ocr_pipeline.formatter import (
    AltoFormatter,
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


# ---------------------------------------------------------------------------
# AltoFormatter
# ---------------------------------------------------------------------------


class TestAltoFormatter:
    """Tests for ALTO XML v4.4 output formatter."""

    ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"

    def test_extension(self) -> None:
        fmt = AltoFormatter()
        assert fmt.extension() == ".xml"

    def test_alto_formatter_basic(self) -> None:
        """Basic test: no blocks, just merged_markdown."""
        fmt = AltoFormatter()
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            merged_markdown="## Hello World\n\nSome text here.",
            metadata={"page_width": 1200, "page_height": 800},
        )
        output = fmt.format(page)

        # Valid XML
        root = ET.fromstring(output.encode("utf-8"))
        assert root.tag == f"{{{self.ALTO_NS}}}alto"

        # Page dimensions
        layout = root.find(f"{{{self.ALTO_NS}}}Layout")
        assert layout is not None
        page_elem = layout.find(f"{{{self.ALTO_NS}}}Page")
        assert page_elem is not None
        assert page_elem.get("WIDTH") == "1200"
        assert page_elem.get("HEIGHT") == "800"

        # Contains markdown text somewhere
        assert "Hello World" in output
        assert "Some text here" in output

        # Contains the TextBlock with the text
        ps = page_elem.find(f"{{{self.ALTO_NS}}}PrintSpace")
        assert ps is not None
        tb = ps.find(f"{{{self.ALTO_NS}}}TextBlock")
        assert tb is not None
        tl = tb.find(f"{{{self.ALTO_NS}}}TextLine")
        assert tl is not None
        string_elem = tl.find(f"{{{self.ALTO_NS}}}String")
        assert string_elem is not None
        content = string_elem.get("CONTENT", "")
        assert "Hello World" in content

    def test_alto_formatter_with_blocks(self) -> None:
        """Blocks with heading + children produce correct TextBlock elements."""
        fmt = AltoFormatter()
        child_block = Block(
            type="text",
            text="Body text here.",
            bbox=(100, 260, 800, 300),
        )
        heading_block = Block(
            type="heading",
            text="Test Heading",
            bbox=(100, 200, 800, 250),
            confidence=0.95,
            children=[child_block],
        )
        eo = EngineOutput(
            engine="surya2",
            text="Test Heading\nBody text here.",
            blocks=[heading_block],
        )
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            merged_markdown="Test Heading\nBody text here.",
            engine_outputs={"surya2": eo},
            metadata={"page_width": 1000, "page_height": 500},
        )
        output = fmt.format(page)

        root = ET.fromstring(output.encode("utf-8"))

        # Should contain a TextBlock for the heading
        ps = root.find(f"{{{self.ALTO_NS}}}Layout/{{{self.ALTO_NS}}}Page/{{{self.ALTO_NS}}}PrintSpace")
        assert ps is not None
        text_blocks = ps.findall(f"{{{self.ALTO_NS}}}TextBlock")
        assert len(text_blocks) >= 1

        # Contains the heading text (extract from DOM; words may be split by SP)
        all_strings = text_blocks[0].iter(f"{{{self.ALTO_NS}}}String")
        heading_words = [s.get("CONTENT", "") for s in all_strings]
        assert "Test" in heading_words
        assert "Heading" in heading_words

        # Should also contain the child body text
        assert len(text_blocks) >= 2  # heading block + child body block
        # Check the child block's text
        child_strings = list(text_blocks[1].iter(f"{{{self.ALTO_NS}}}String"))
        child_text = " ".join(s.get("CONTENT", "") for s in child_strings)
        assert "Body text here" in child_text

        # Confidence attribute (WC) on String element
        all_strings = root.iter(f"{{{self.ALTO_NS}}}String")
        wc_found = False
        for s in all_strings:
            if s.get("WC"):
                assert s.get("WC") == "0.9500"
                wc_found = True
                break
        assert wc_found, "Expected WC (word confidence) attribute on String element"

    def test_alto_formatter_missing_dimensions(self) -> None:
        """When page dimensions are missing, default values are used (no crash)."""
        fmt = AltoFormatter()
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            merged_markdown="Some content",
            metadata={},
        )
        output = fmt.format(page)

        root = ET.fromstring(output.encode("utf-8"))
        page_elem = root.find(f"{{{self.ALTO_NS}}}Layout/{{{self.ALTO_NS}}}Page")
        assert page_elem is not None
        # Default dimensions (US Letter at 300 DPI)
        assert page_elem.get("WIDTH") == "2550"
        assert page_elem.get("HEIGHT") == "3300"

    def test_alto_formatter_empty(self) -> None:
        """Empty merged_markdown produces valid minimal ALTO XML."""
        fmt = AltoFormatter()
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            merged_markdown="",
            metadata={"page_width": 100, "page_height": 200},
        )
        output = fmt.format(page)

        # Must be valid XML
        root = ET.fromstring(output.encode("utf-8"))
        assert root.tag == f"{{{self.ALTO_NS}}}alto"

        # No TextBlock when there's no text
        ps = root.find(f"{{{self.ALTO_NS}}}Layout/{{{self.ALTO_NS}}}Page/{{{self.ALTO_NS}}}PrintSpace")
        assert ps is not None
        tb = ps.find(f"{{{self.ALTO_NS}}}TextBlock")
        assert tb is None  # No text content = no TextBlock

    def test_alto_formatter_figure_block(self) -> None:
        """Figure blocks produce Illustration elements (no text)."""
        fmt = AltoFormatter()
        figure_block = Block(
            type="figure",
            text="",
            bbox=(50, 50, 500, 400),
        )
        eo = EngineOutput(
            engine="surya2",
            text="",
            blocks=[figure_block],
        )
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            engine_outputs={"surya2": eo},
            metadata={"page_width": 1000, "page_height": 800},
        )
        output = fmt.format(page)

        root = ET.fromstring(output.encode("utf-8"))
        illustrations = root.iter(f"{{{self.ALTO_NS}}}Illustration")
        ill_list = list(illustrations)
        assert len(ill_list) >= 1
        assert ill_list[0].get("HPOS") == "50"
        assert ill_list[0].get("VPOS") == "50"

    def test_alto_formatter_table_block(self) -> None:
        """Table blocks produce ComposedBlock elements."""
        fmt = AltoFormatter()
        table_block = Block(
            type="table",
            text="Header | Value\nA | 1",
            bbox=(10, 10, 990, 300),
        )
        eo = EngineOutput(
            engine="surya2",
            text="Header | Value\nA | 1",
            blocks=[table_block],
        )
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            engine_outputs={"surya2": eo},
            metadata={"page_width": 1000, "page_height": 800},
        )
        output = fmt.format(page)

        root = ET.fromstring(output.encode("utf-8"))
        composed = root.find(f".//{{{self.ALTO_NS}}}ComposedBlock")
        assert composed is not None

    def test_alto_formatter_no_blocks_single_engine(self) -> None:
        """Engine output without blocks uses merged_markdown fallback."""
        fmt = AltoFormatter()
        eo = EngineOutput(engine="marker", text="Plain text output")
        page = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            merged_markdown="Plain text output",
            engine_outputs={"marker": eo},
            metadata={"page_width": 800, "page_height": 600},
        )
        output = fmt.format(page)

        root = ET.fromstring(output.encode("utf-8"))
        ps = root.find(f"{{{self.ALTO_NS}}}Layout/{{{self.ALTO_NS}}}Page/{{{self.ALTO_NS}}}PrintSpace")
        assert ps is not None
        tb = ps.find(f"{{{self.ALTO_NS}}}TextBlock")
        assert tb is not None
        string_elem = tb.find(f"{{{self.ALTO_NS}}}TextLine/{{{self.ALTO_NS}}}String")
        assert string_elem is not None
        assert "Plain text output" in string_elem.get("CONTENT", "")

    def test_get_formatter_alto(self) -> None:
        """get_formatter('alto') returns AltoFormatter."""
        fmt = get_formatter("alto")
        assert isinstance(fmt, AltoFormatter)
