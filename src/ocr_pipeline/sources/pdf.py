"""PDF document source — wraps the existing PyMuPDF rendering/extraction."""

from __future__ import annotations

from pathlib import Path

from .base import DocumentSource


class PdfSource(DocumentSource):
    """Document source for native PDF files.

    Delegates to the existing :func:`ocr_pipeline.renderer.render_page` and
    :func:`ocr_pipeline.extractor.extract_page_text` functions so the PDF
    path remains zero-regression.
    """

    @property
    def source_format(self) -> str:
        return "pdf"

    @property
    def source_mimetype(self) -> str:
        return "application/pdf"

    @property
    def page_count(self) -> int:
        try:
            import fitz

            doc = fitz.open(str(self.path))
            try:
                return doc.page_count
            finally:
                doc.close()
        except Exception:
            return 0  # Consistent with other sources: 0 = failed/corrupt

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        from ocr_pipeline.renderer import render_page as _render_page

        return _render_page(self.path, page_index, output_dir, dpi=dpi)

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        from ocr_pipeline.extractor import extract_page_text as _extract

        text, saved = _extract(self.path, page_index, output_dir, flags=flags)
        return text, saved
