"""Output formatters for the OCR pipeline. Terminal step after OCR/merge."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .models import MetadataResult, PageResult


class MarkdownFormatter:
    """Produces markdown output (passthrough from merged markdown)."""

    def format(self, page: PageResult) -> str:
        text = page.merged_markdown
        if page.confidence is not None:
            conf_pct = round(page.confidence * 100, 1)
            conf_line = f"<!-- OCR confidence: {conf_pct}% -->\n\n"
            text = conf_line + text
        return text

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


@dataclass
class YamlFrontmatterFormatter:
    """Produces per-PDF markdown with YAML frontmatter from GROBID metadata.

    Unlike :class:`MarkdownFormatter` (per-page), this formatter operates at
    the document level — it concatenates all pages of a PDF into one markdown
    file with a YAML frontmatter block containing structured metadata (title,
    authors, DOI, journal, etc.).

    Usage::

        fmt = YamlFrontmatterFormatter()
        md = fmt.format(metadata=grobid_result, pages=page_results)
        path.write_text(md)
    """

    def format(self, metadata: MetadataResult | None, pages: list[PageResult]) -> str:
        """Concatenate all *pages* with YAML frontmatter from *metadata*.

        Args:
            metadata: Structured metadata (may be ``None`` for an empty frontmatter).
            pages: Processed pages (only ``merged_markdown`` is used).

        Returns:
            A complete markdown string: ``---\\n<yaml>\\n---\\n\\n<body>``.
        """
        frontmatter: dict[str, Any] = {}
        if metadata:
            if metadata.title:
                frontmatter["title"] = metadata.title
            if metadata.authors:
                frontmatter["authors"] = metadata.authors
            if metadata.doi:
                frontmatter["doi"] = metadata.doi
            if metadata.journal:
                frontmatter["journal"] = metadata.journal
            if metadata.volume:
                frontmatter["volume"] = metadata.volume
            if metadata.issue:
                frontmatter["issue"] = metadata.issue
            if metadata.year:
                frontmatter["year"] = metadata.year
            if metadata.abstract:
                frontmatter["abstract"] = metadata.abstract[:500]
            if metadata.keywords:
                frontmatter["keywords"] = metadata.keywords

        import yaml as yaml_lib

        yaml_str = yaml_lib.dump(
            frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
        body = "\n\n".join(p.merged_markdown for p in pages if p.merged_markdown.strip())
        return f"---\n{yaml_str}---\n\n{body}"

    def extension(self) -> str:
        return ".md"


_FORMATTERS: dict[str, Any] = {
    "markdown": MarkdownFormatter(),
    "json": JsonFormatter(),
}


def get_formatter(fmt: str):
    """Return formatter instance for the given format name."""
    if fmt not in _FORMATTERS:
        raise ValueError(f"Unknown output format: {fmt}. Valid: {list(_FORMATTERS.keys())}")
    return _FORMATTERS[fmt]
