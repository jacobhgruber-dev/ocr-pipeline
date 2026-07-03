"""SVG document source — vector graphics with embedded text.

Parses SVG files via lxml, extracting text content from ``<text>``,
``<tspan>`` elements and metadata from ``<title>``, ``<desc>``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class SvgSource(DocumentSource):
    """Document source for SVG files (``.svg``, ``.svgz``).

    Extracts text elements and metadata.  SVG text is already
    machine-readable — no OCR needed unless text is rendered as paths.
    """

    _text_cache: str | None = None
    _meta_cache: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        return "svg"

    @property
    def source_mimetype(self) -> str:
        return "image/svg+xml"

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> tuple[str, dict[str, str]]:
        if self._text_cache is not None:
            return self._text_cache, self._meta_cache or {}

        from lxml import etree

        try:
            raw = self.path.read_text(encoding="utf-8", errors="replace")
            doc = etree.fromstring(raw.encode("utf-8"))
        except Exception:
            self._text_cache = ""
            self._meta_cache = {}
            return "", {}

        meta: dict[str, str] = {}
        text_parts: list[str] = []

        svg_ns = "{http://www.w3.org/2000/svg}"

        # Title and description
        for tag in ("title", "desc"):
            el = doc.find(f"{svg_ns}{tag}") or doc.find(tag)
            if el is not None and el.text:
                meta[tag] = el.text.strip()

        # Text elements
        for el in doc.iter():
            tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if tag in ("text", "tspan", "textPath"):
                content = el.text or ""
                for child in el:
                    if child.tail:
                        content += " " + child.tail.strip()
                content = content.strip()
                if content:
                    text_parts.append(content)

        self._text_cache = "\n".join(text_parts)
        self._meta_cache = meta
        return self._text_cache, meta

    def extract_metadata(self) -> MetadataResult:
        _text, meta = self._parse()

        return MetadataResult(
            title=meta.get("title", "") or self.path.stem,
            document_type="vector-graphic",
            extraction_method="svg-parsing",
            source_info=SourceInfo(
                format="svg",
                page_count=1,
                mimetype="image/svg+xml",
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("SvgSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _meta = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(f"# SVG: {self.path.name}\n\n{text}", encoding="utf-8")

        return text, out_path
