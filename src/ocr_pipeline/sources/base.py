"""Abstract ``DocumentSource`` protocol for multi-format document ingestion.

Every source implementation provides:
* ``page_count`` — how many logical pages the document has
* ``render_page(page_index, output_dir, dpi)`` — produce a high-resolution
  PNG for the given 0-based page number
* ``extract_text(page_index, output_dir, flags)`` — try to extract
  machine-readable text without rendering (the "fast path")

When a format has no native text-extraction path (e.g. JPEG), ``extract_text``
returns ``("", None)`` and the pipeline falls through to rendering + OCR.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class DocumentSource(ABC):
    """Protocol for a structured, page-oriented document.

    Mimics the original ``Pipeline._process_single_page()`` contract: each
    page is independently rendered or text-extracted, so the pipeline core
    (``PageProcessor``) doesn't need to know about the container format.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    @property
    @abstractmethod
    def source_format(self) -> str:
        """Short lowercase format name (``"pdf"``, ``"epub"``, ``"docx"``, ...)."""
        ...

    @property
    @abstractmethod
    def source_mimetype(self) -> str:
        """IANA media type (e.g. ``"application/pdf"``)."""
        ...

    @property
    @abstractmethod
    def page_count(self) -> int:
        """Number of logical pages."""
        ...

    @abstractmethod
    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        """Render a single page to a PNG file.

        Args:
            page_index: 0-based page number.
            output_dir: Directory to write the PNG to.
            dpi: Rendering resolution (default 300).

        Returns:
            Path to the rendered PNG.

        Raises:
            OcrPipelineError: If rendering fails for any reason.
        """
        ...

    @abstractmethod
    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        """Try to extract machine-readable text without rendering.

        Args:
            page_index: 0-based page number.
            output_dir: Directory to save extracted text.
            flags: Format-specific extraction flags.

        Returns:
            ``(text, saved_path)`` where *saved_path* is the written file
            or ``None`` if text extraction is not supported for this format.
        """
        ...
