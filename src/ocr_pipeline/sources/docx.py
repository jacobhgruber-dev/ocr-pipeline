"""DOCX document source — extract text and metadata from Word documents.

Each paragraph group separated by page breaks is treated as a logical page.
Text extraction returns formatted markdown.  Rendering delegates to a
PDF conversion step (the pipeline should convert to PDF first).
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.errors import RenderError

from .base import DocumentSource

logger = logging.getLogger(__name__)


class DocxSource(DocumentSource):
    """Document source for Microsoft Word .docx files.

    Text extraction aggregates paragraphs between explicit page breaks.
    Rendering is not directly supported — convert to PDF first.
    """

    _paragraphs_loaded: list[str] | None = None

    @property
    def source_format(self) -> str:
        return "docx"

    @property
    def source_mimetype(self) -> str:
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def _load_paragraphs(self) -> list[str]:
        """Load all paragraphs from the DOCX file, caching the result."""
        if self._paragraphs_loaded is not None:
            return self._paragraphs_loaded

        from docx import Document

        try:
            doc = Document(str(self.path))
        except Exception as exc:
            raise RenderError(f"Failed to open DOCX: {self.path}") from exc
        paragraphs: list[str] = []

        for para in doc.paragraphs:
            text = para.text
            if para.style is not None and para.style.name and para.style.name.startswith("Heading"):
                level = para.style.name.replace("Heading ", "")
                if len(level) == 1 and level.isdigit():
                    hashes = "#" * int(level)
                    text = f"{hashes} {text}"
            paragraphs.append(text)

        self._paragraphs_loaded = paragraphs
        return paragraphs

    @property
    def page_count(self) -> int:
        paragraphs = self._load_paragraphs()
        # Count explicit page breaks
        count = 1
        for text in paragraphs:
            if "\f" in text:
                count += 1
        return count

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError(
            "DocxSource.render_page not yet implemented — "
            "convert to PDF before OCR or use text extraction path."
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        paragraphs = self._load_paragraphs()

        # Split by page breaks to build page content
        pages: list[list[str]] = []
        current: list[str] = []
        for text in paragraphs:
            if "\f" in text:
                # Page break within paragraph — split on all breaks
                parts = text.split("\f")
                for i, part in enumerate(parts):
                    if i > 0:
                        pages.append(current)
                        current = []
                    if part.strip():
                        current.append(part)
            else:
                current.append(text)
        if current:
            pages.append(current)

        if page_index < 0 or page_index >= len(pages):
            raise RenderError(f"DOCX page index {page_index} out of range ({len(pages)} pages)")

        page_text = "\n\n".join(p for p in pages[page_index] if p.strip())

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"page_{page_index + 1:04d}_final.md"
        out_path.write_text(page_text, encoding="utf-8")

        return page_text, out_path
