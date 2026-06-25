"""Output formatters for the OCR pipeline. Terminal step after OCR/merge."""

from __future__ import annotations

import json
from typing import Any

from .models import PageResult


class MarkdownFormatter:
    """Produces markdown output (passthrough from merged markdown)."""

    def format(self, page: PageResult) -> str:
        return page.merged_markdown

    def extension(self) -> str:
        return ".md"


class JsonFormatter:
    """Produces structured JSON with markdown + blocks + metadata."""

    def format(self, page: PageResult) -> str:
        doc: dict[str, Any] = {
            "page_index": page.page_index,
            "page_label": page.page_label,
            "markdown": page.merged_markdown,
            "status": page.status.value,
            "engine_outputs": {},
        }
        for name, eo in page.engine_outputs.items():
            entry: dict[str, Any] = {"text": eo.text, "error": eo.error}
            if eo.blocks:
                entry["blocks"] = [b.to_dict() for b in eo.blocks]
            doc["engine_outputs"][name] = entry
        return json.dumps(doc, indent=2, ensure_ascii=False)

    def extension(self) -> str:
        return ".json"


_FORMATTERS: dict[str, Any] = {
    "markdown": MarkdownFormatter(),
    "json": JsonFormatter(),
}


def get_formatter(fmt: str):
    """Return formatter instance for the given format name."""
    if fmt not in _FORMATTERS:
        raise ValueError(f"Unknown output format: {fmt}. Valid: {list(_FORMATTERS.keys())}")
    return _FORMATTERS[fmt]
