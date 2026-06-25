"""Tests for output formatters — MarkdownFormatter and JsonFormatter."""

from __future__ import annotations

import json

import pytest

from ocr_pipeline.formatter import (
    JsonFormatter,
    MarkdownFormatter,
    get_formatter,
)
from ocr_pipeline.models import Block, EngineOutput, PageResult, PageStatus


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
