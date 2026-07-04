"""Output formatters for the OCR pipeline. Terminal step after OCR/merge."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar

import lxml.etree as ET

from .models import Block, MetadataResult, PageResult

logger = logging.getLogger(__name__)


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

    _FIELD_MAP: ClassVar[list[tuple[str, str]]] = [
        ("title", "title"),
        ("authors", "authors"),
        ("document_type", "document_type"),
        ("language", "language"),
        ("doi", "doi"),
        ("isbn", "isbn"),
        ("journal", "journal"),
        ("publisher", "publisher"),
        ("volume", "volume"),
        ("issue", "issue"),
        ("year", "year"),
        ("date", "date"),
        ("court", "court"),
        ("docket_number", "docket_number"),
        ("edition", "edition"),
        ("series", "series"),
        ("part_number", "part_number"),
        ("revision", "revision"),
        ("pages", "pages"),
        ("abstract", "abstract"),
        ("keywords", "keywords"),
        ("identifiers", "identifiers"),
    ]

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
            for attr, key in self._FIELD_MAP:
                val = getattr(metadata, attr, None)
                if val or (isinstance(val, list) and val):
                    if attr == "abstract" and isinstance(val, str) and len(val) > 500:
                        val = val[:500]
                    frontmatter[key] = val

        import yaml as yaml_lib

        yaml_str = yaml_lib.dump(
            frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
        body = "\n\n".join(p.merged_markdown for p in pages if p.merged_markdown.strip())
        return f"---\n{yaml_str}---\n\n{body}"

    def extension(self) -> str:
        return ".md"


class AltoFormatter:
    """Produces ALTO XML v4.4 output from structured page results."""

    def __init__(self):
        self._id_counter = 0

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"elem_{self._id_counter}"

    def extension(self) -> str:
        return ".xml"

    def format(self, page: PageResult) -> str:
        # Get page dimensions
        page_width = page.metadata.get("page_width")
        page_height = page.metadata.get("page_height")

        if page_width is None or page_height is None:
            page_width = 2550
            page_height = 3300
            logger.warning(
                "Page dimensions not found in metadata for %s, using defaults (%d x %d)",
                page.page_label,
                page_width,
                page_height,
            )
        else:
            page_width = int(page_width)
            page_height = int(page_height)

        # ALTO namespace
        NS = "http://www.loc.gov/standards/alto/ns-v4#"
        XSI = "http://www.w3.org/2001/XMLSchema-instance"

        alto = ET.Element("alto", nsmap={None: NS, "xsi": XSI})
        alto.set(
            f"{{{XSI}}}schemaLocation", f"{NS} http://www.loc.gov/standards/alto/v4/alto-4-4.xsd"
        )

        # --- Description ---
        desc = ET.SubElement(alto, "Description")
        mu = ET.SubElement(desc, "MeasurementUnit")
        mu.text = "pixel"
        sii = ET.SubElement(desc, "sourceImageInformation")
        fn = ET.SubElement(sii, "fileName")
        fn.text = f"{page.page_label}.png"

        ocr_proc = ET.SubElement(desc, "OCRProcessing", ID="ocr_1")
        ocr_step = ET.SubElement(ocr_proc, "ocrProcessingStep")

        # processingDateTime
        if page.completed_at:
            pdt_text = page.completed_at
        else:
            pdt_text = datetime.now(timezone.utc).isoformat()
        pdt = ET.SubElement(ocr_step, "processingDateTime")
        pdt.text = pdt_text

        ps = ET.SubElement(ocr_step, "processingSoftware")
        sc = ET.SubElement(ps, "softwareCreator")
        sc.text = "ocr-pipeline v0.2.0"

        # --- Layout ---
        layout = ET.SubElement(alto, "Layout")
        page_elem = ET.SubElement(
            layout,
            "Page",
            ID="page_1",
            PHYSICAL_IMG_NR="1",
            HEIGHT=str(page_height),
            WIDTH=str(page_width),
        )
        ps_elem = ET.SubElement(
            page_elem,
            "PrintSpace",
            HPOS="0",
            VPOS="0",
            WIDTH=str(page_width),
            HEIGHT=str(page_height),
        )

        # Get blocks from engine outputs
        blocks = None
        for engine_name in ("surya2", "marker", "google_doc_ai", "mathpix", "tesseract"):
            eo = page.engine_outputs.get(engine_name)
            if eo and eo.blocks:
                blocks = eo.blocks
                break

        if blocks:
            # Build ALTO blocks
            for block in blocks:
                self._build_block(ps_elem, block, page_width, page_height)
        else:
            # No blocks -- create single TextBlock with merged_markdown text
            text = self._strip_html_comments(page.merged_markdown).strip()
            if text:
                tb_attrs = {
                    "HPOS": "0",
                    "VPOS": "0",
                    "WIDTH": str(page_width),
                    "HEIGHT": str(page_height),
                }
                tb = ET.SubElement(ps_elem, "TextBlock", ID=self._next_id(), **tb_attrs)
                tl = ET.SubElement(
                    tb,
                    "TextLine",
                    HPOS="0",
                    VPOS="0",
                    WIDTH=str(page_width),
                    HEIGHT=str(page_height),
                )
                s_attrs = {
                    "CONTENT": text,
                    "HPOS": "0",
                    "VPOS": "0",
                    "WIDTH": str(page_width),
                    "HEIGHT": str(page_height),
                }
                ET.SubElement(tl, "String", **s_attrs)

        # Serialize
        xml_bytes = ET.tostring(alto, xml_declaration=True, encoding="UTF-8", pretty_print=True)
        return xml_bytes.decode("utf-8")

    @staticmethod
    def _bbox_to_alto(bbox: tuple[float, float, float, float]) -> dict:
        x0, y0, x1, y1 = bbox
        return {
            "HPOS": str(int(x0)),
            "VPOS": str(int(y0)),
            "WIDTH": str(max(0, int(x1 - x0))),
            "HEIGHT": str(max(0, int(y1 - y0))),
        }

    @staticmethod
    def _strip_html_comments(text: str) -> str:
        return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    def _build_block(self, parent, block, page_width, page_height):
        """Add a block element to *parent*, recursing into children."""
        bbox_attrs = (
            self._bbox_to_alto(block.bbox)
            if block.bbox
            else {
                "HPOS": "0",
                "VPOS": "0",
                "WIDTH": str(page_width),
                "HEIGHT": str(page_height),
            }
        )

        block_type = block.type.lower() if block.type else "text"

        if block_type == "table":
            # ComposedBlock for tables
            cb = ET.SubElement(parent, "ComposedBlock", ID=self._next_id(), **bbox_attrs)
            if block.children:
                for child in block.children:
                    self._build_block(cb, child, page_width, page_height)
            else:
                self._add_text_content(cb, block, page_width, page_height)
        elif block_type == "figure":
            # Illustration element -- bbox only, no text
            ET.SubElement(parent, "Illustration", ID=self._next_id(), **bbox_attrs)
            # Still process children if any exist (unusual but safe)
            for child in block.children:
                self._build_block(parent, child, page_width, page_height)
        elif block_type in ("text", "heading", "footer", "header", "equation"):
            tb = ET.SubElement(parent, "TextBlock", ID=self._next_id(), **bbox_attrs)
            self._add_text_content(tb, block, page_width, page_height)
            # Recurse into children
            for child in block.children:
                self._build_block(parent, child, page_width, page_height)
        else:
            # Default/unknown -> TextBlock
            tb = ET.SubElement(parent, "TextBlock", ID=self._next_id(), **bbox_attrs)
            self._add_text_content(tb, block, page_width, page_height)
            for child in block.children:
                self._build_block(parent, child, page_width, page_height)

    @staticmethod
    def _add_text_content(tb, block, page_width, page_height):
        """Add TextLine content to a TextBlock element."""
        text = AltoFormatter._strip_html_comments(block.text or "").strip()
        if not text:
            return
        # Default attrs if no bbox
        block_bbox = (
            AltoFormatter._bbox_to_alto(block.bbox)
            if block.bbox
            else {
                "HPOS": "0",
                "VPOS": "0",
                "WIDTH": str(page_width),
                "HEIGHT": str(int(page_height * 0.1)),
            }
        )
        tl = ET.SubElement(tb, "TextLine", **block_bbox)

        has_word_bboxes = block.words and any(w.bbox is not None for w in block.words)

        if has_word_bboxes:
            # Word-level bbox path — each word gets its own <String> element
            for i, word in enumerate(block.words):
                if word.bbox is not None:
                    word_attrs = AltoFormatter._bbox_to_alto(word.bbox)
                else:
                    word_attrs = dict(block_bbox)
                word_attrs["CONTENT"] = word.text
                if word.confidence > 0:
                    word_attrs["WC"] = f"{word.confidence:.4f}"
                ET.SubElement(tl, "String", **word_attrs)
                if i < len(block.words) - 1:
                    ET.SubElement(tl, "SP")
        else:
            # Fallback — split text into words with block-level bbox
            words = text.split()
            wc_attr = {}
            if block.confidence > 0:
                wc_attr = {"WC": f"{block.confidence:.4f}"}

            if len(words) <= 1:
                s_attrs = {"CONTENT": text, **block_bbox}
                s_attrs.update(wc_attr)
                ET.SubElement(tl, "String", **s_attrs)
            else:
                for i, word in enumerate(words):
                    s_attrs = {
                        "CONTENT": word,
                        "HPOS": block_bbox["HPOS"],
                        "VPOS": block_bbox["VPOS"],
                        "WIDTH": block_bbox["WIDTH"],
                        "HEIGHT": block_bbox["HEIGHT"],
                    }
                    s_attrs.update(wc_attr)
                    ET.SubElement(tl, "String", **s_attrs)
                    if i < len(words) - 1:
                        ET.SubElement(tl, "SP")


class HocrFormatter:
    """hOCR output format — XHTML with CSS classes for OCR results.

    Follows the hOCR spec: https://github.com/kba/hocr-spec

    Output is valid XHTML 1.0 Transitional with standard hOCR CSS
    class names (``ocr_page``, ``ocr_carea``, ``ocr_par``, ``ocr_line``,
    ``ocrx_word``, ``ocr_table``, ``ocr_image``).
    """

    # Block type -> hOCR CSS class mapping
    _BLOCK_CLASS_MAP: dict[str, str] = {
        "text": "ocr_carea",
        "heading": "ocr_carea",
        "header": "ocr_carea",
        "footer": "ocr_carea",
        "table": "ocr_table",
        "figure": "ocr_image",
        "equation": "ocr_carea",
    }

    def __init__(self):
        self._id_counter = 0

    def _next_id(self, prefix: str) -> str:
        self._id_counter += 1
        return f"{prefix}_{self._id_counter}"

    def extension(self) -> str:
        return ".html"

    def format(self, page: PageResult) -> str:
        # Page dimensions
        page_width = int(page.metadata.get("page_width", 2550))
        page_height = int(page.metadata.get("page_height", 3300))

        # Build HTML document using lxml.etree
        NS = "http://www.w3.org/1999/xhtml"
        html = ET.Element(
            "html",
            nsmap={None: NS, "xml": "http://www.w3.org/XML/1998/namespace"},
        )
        html.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        html.set("lang", "en")

        head = ET.SubElement(html, "head")
        title = ET.SubElement(head, "title")
        title.text = f"OCR Output \u2014 {page.page_label}"

        meta_system = ET.SubElement(head, "meta")
        meta_system.set("name", "ocr-system")
        meta_system.set("content", "ocr-pipeline v0.2.0")

        meta_caps = ET.SubElement(head, "meta")
        meta_caps.set("name", "ocr-capabilities")
        meta_caps.set("content", "ocr_page ocr_carea ocr_par ocr_line ocrx_word")

        body = ET.SubElement(html, "body")

        # Build page div
        page_title_attr = (
            f"image {page.page_label}.png; bbox 0 0 {page_width} {page_height}; "
            f"ppageno {page.page_index + 1}"
        )
        page_div = ET.SubElement(
            body,
            "div",
            {
                "class": "ocr_page",
                "id": "page_1",
                "title": page_title_attr,
            },
        )

        # Get blocks from engine outputs (same priority as ALTO)
        blocks = None
        for engine_name in ("surya2", "marker", "google_doc_ai", "mathpix", "tesseract"):
            eo = page.engine_outputs.get(engine_name)
            if eo and eo.blocks:
                blocks = eo.blocks
                break

        if blocks:
            for block in blocks:
                self._build_block(page_div, block, page_width, page_height)
        else:
            # No blocks -- create single ocr_carea with merged_markdown text
            text = self._strip_markdown_formatting(page.merged_markdown).strip()
            if text:
                area_title = f"bbox 0 0 {page_width} {page_height}"
                area_div = ET.SubElement(
                    page_div,
                    "div",
                    {
                        "class": "ocr_carea",
                        "id": self._next_id("block"),
                        "title": area_title,
                    },
                )
                par = ET.SubElement(
                    area_div,
                    "p",
                    {
                        "class": "ocr_par",
                        "id": self._next_id("par"),
                        "title": area_title,
                    },
                )
                line_span = ET.SubElement(
                    par,
                    "span",
                    {
                        "class": "ocr_line",
                        "id": self._next_id("line"),
                        "title": area_title,
                    },
                )
                self._add_words(line_span, text, page_width, page_height, 0.0)

        # Build XHTML document
        doctype = (
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"\n'
            '  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
        )
        xml_str = ET.tostring(html, xml_declaration=True, encoding="UTF-8", pretty_print=True)
        # lxml adds its own XML declaration; we want a custom DOCTYPE
        result = xml_str.decode("utf-8")
        # Replace lxml's default XML decl + remove it for a clean combination
        # We'll build the full output: XML decl + DOCTYPE + HTML
        result = (
            '<?xml version="1.0" encoding="UTF-8"?>\n' + doctype + "\n" + result.split("\n", 1)[1]
        )
        return result

    def _build_block(self, parent, block: Block, page_width: int, page_height: int) -> None:
        """Build hOCR elements for a block, recursing into children."""
        bbox = block.bbox if block.bbox else (0, 0, page_width, page_height)
        x0, y0, x1, y1 = (int(v) for v in bbox)
        bbox_title = f"bbox {x0} {y0} {x1} {y1}"

        block_type = block.type.lower() if block.type else "text"
        hocr_class = self._BLOCK_CLASS_MAP.get(block_type, "ocr_carea")

        if block_type == "table":
            # Table block: ocr_table div (like ocr_carea but for tables)
            area_div = ET.SubElement(
                parent,
                "div",
                {
                    "class": hocr_class,
                    "id": self._next_id("table"),
                    "title": bbox_title,
                },
            )
            if block.children:
                for child in block.children:
                    self._build_block(area_div, child, page_width, page_height)
            else:
                self._add_text_to_block(area_div, block, x0, y0, x1, y1)
        elif block_type == "figure":
            # Image block: ocr_image div (no text content)
            ET.SubElement(
                parent,
                "div",
                {
                    "class": hocr_class,
                    "id": self._next_id("image"),
                    "title": bbox_title,
                },
            )
            for child in block.children:
                self._build_block(parent, child, page_width, page_height)
        elif block_type in ("text", "heading", "header", "footer", "equation"):
            # Standard content block
            area_div = ET.SubElement(
                parent,
                "div",
                {
                    "class": hocr_class,
                    "id": self._next_id("block"),
                    "title": bbox_title,
                },
            )
            self._add_text_to_block(area_div, block, x0, y0, x1, y1)
            for child in block.children:
                self._build_block(parent, child, page_width, page_height)
        else:
            # Unknown type -> ocr_carea fallback
            area_div = ET.SubElement(
                parent,
                "div",
                {
                    "class": "ocr_carea",
                    "id": self._next_id("block"),
                    "title": bbox_title,
                },
            )
            self._add_text_to_block(area_div, block, x0, y0, x1, y1)
            for child in block.children:
                self._build_block(parent, child, page_width, page_height)

    def _add_text_to_block(
        self, area_div, block: Block, x0: int, y0: int, x1: int, y1: int
    ) -> None:
        """Add paragraph, line, and word elements for a block's text."""
        text = self._strip_markdown_formatting(block.text or "").strip()
        if not text:
            return

        bbox_title = f"bbox {x0} {y0} {x1} {y1}"
        confidence = getattr(block, "confidence", 0.0) or 0.0

        has_word_bboxes = block.words and any(w.bbox is not None for w in block.words)

        par = ET.SubElement(
            area_div,
            "p",
            {
                "class": "ocr_par",
                "id": self._next_id("par"),
                "title": bbox_title,
            },
        )
        line_span = ET.SubElement(
            par,
            "span",
            {
                "class": "ocr_line",
                "id": self._next_id("line"),
                "title": bbox_title,
            },
        )

        if has_word_bboxes:
            # Word-level bbox path — each word gets its own ocrx_word span
            for i, word in enumerate(block.words):
                if word.bbox is not None:
                    wx0, wy0, wx1, wy1 = (int(v) for v in word.bbox)
                    word_title = f"bbox {wx0} {wy0} {wx1} {wy1}"
                else:
                    word_title = bbox_title
                if word.confidence > 0:
                    word_title += f"; x_wconf {int(round(word.confidence * 100))}"
                span = ET.SubElement(
                    line_span,
                    "span",
                    {
                        "class": "ocrx_word",
                        "id": self._next_id("word"),
                        "title": word_title,
                    },
                )
                span.text = word.text
                if i < len(block.words) - 1:
                    span.tail = " "
        else:
            # Fallback — split text into words with block-level bbox
            self._add_words(line_span, text, x1, y1, confidence)

    def _add_words(
        self,
        parent,
        text: str,
        width: int,
        height: int,
        confidence: float,
    ) -> None:
        """Add ocrx_word spans for each word in text, with space tails between."""
        words = text.split()
        if not words:
            return

        x_wconf = f"x_wconf {int(round(confidence * 100))}" if confidence > 0 else ""

        for i, word in enumerate(words):
            title_parts = [f"bbox 0 0 {width} {height}"]
            if x_wconf:
                title_parts.append(x_wconf)
            word_title = "; ".join(title_parts)

            span = ET.SubElement(
                parent,
                "span",
                {
                    "class": "ocrx_word",
                    "id": self._next_id("word"),
                    "title": word_title,
                },
            )
            span.text = word

            # Add space between words as tail text on the word element
            if i < len(words) - 1:
                span.tail = " "

    @staticmethod
    def _strip_markdown_formatting(text: str) -> str:
        """Remove HTML comments and basic markdown formatting from text."""
        import re

        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        return text


_FORMATTERS: dict[str, Any] = {
    "markdown": MarkdownFormatter(),
    "json": JsonFormatter(),
    "alto": AltoFormatter(),
    "hocr": HocrFormatter(),
}


def get_formatter(fmt: str):
    """Return formatter instance for the given format name."""
    if fmt not in _FORMATTERS:
        raise ValueError(f"Unknown output format: {fmt}. Valid: {list(_FORMATTERS.keys())}")
    return _FORMATTERS[fmt]
