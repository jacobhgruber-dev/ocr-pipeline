"""Multi-format document source implementations.

Usage::

    from ocr_pipeline.sources import detect_source, DocumentSource

    source = detect_source(Path("/data/report.docx"))
    for i in range(source.page_count):
        text, path = source.extract_text(i, output_dir)

Public API
----------
* :func:`detect_source` — factory that picks the right implementation
  based on file extension and content magic bytes.
* :class:`DocumentSource` — abstract base / protocol.
* All concrete implementations are imported here for convenience:

  - :class:`PdfSource`
  - :class:`ImageSource`
  - :class:`EpubSource`
  - :class:`DocxSource`
  - :class:`TxtSource`
  - :class:`CsvSource`
  - :class:`ExcelSource`
  - :class:`PptxSource`
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.errors import ConfigError

from .base import DocumentSource
from .csv_source import CsvSource
from .docx import DocxSource
from .epub import EpubSource
from .excel import ExcelSource
from .html import HtmlSource
from .image import ImageSource
from .latex import LatexSource
from .markdown import MarkdownSource
from .pdf import PdfSource
from .pptx import PptxSource
from .txt import TxtSource

logger = logging.getLogger(__name__)

__all__ = [
    "CsvSource",
    "DocumentSource",
    "DocxSource",
    "EpubSource",
    "ExcelSource",
    "HtmlSource",
    "ImageSource",
    "LatexSource",
    "MarkdownSource",
    "PdfSource",
    "PptxSource",
    "TxtSource",
    "detect_source",
]

# ---------------------------------------------------------------------------
# Extension → source-class mapping (simple, fast)
# ---------------------------------------------------------------------------

_EXTENSION_MAP: dict[str, type[DocumentSource]] = {
    ".pdf": PdfSource,
    ".png": ImageSource,
    ".jpg": ImageSource,
    ".jpeg": ImageSource,
    ".tiff": ImageSource,
    ".tif": ImageSource,
    ".bmp": ImageSource,
    ".webp": ImageSource,
    ".epub": EpubSource,
    ".docx": DocxSource,
    ".txt": TxtSource,
    ".md": MarkdownSource,
    ".markdown": MarkdownSource,
    ".rst": TxtSource,
    ".text": TxtSource,
    ".html": HtmlSource,
    ".htm": HtmlSource,
    ".xhtml": HtmlSource,
    ".tex": LatexSource,
    ".latex": LatexSource,
    ".csv": CsvSource,
    ".tsv": CsvSource,
    ".tab": CsvSource,
    ".xlsx": ExcelSource,
    ".xls": ExcelSource,
    ".xlsm": ExcelSource,
    ".pptx": PptxSource,
    ".ppt": PptxSource,
}


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def detect_source(path: Path) -> DocumentSource:
    """Create the right ``DocumentSource`` for *path* based on extension.

    Uses the extension table first.  For ambiguous extensions (or when
    the type cannot be determined from extension alone) falls back to
    content-based detection via ``filetype``.

    Args:
        path: File path to inspect.

    Returns:
        A concrete ``DocumentSource`` instance.

    Raises:
        ConfigError: If the file type is not recognized or unsupported.
    """
    ext = path.suffix.lower()

    if ext in _EXTENSION_MAP:
        source_cls = _EXTENSION_MAP[ext]
        logger.debug("detect_source: %s -> %s (extension)", path.name, source_cls.__name__)
        return source_cls(path)

    # Fallback: bytes-based detection via filetype library
    try:
        import filetype

        kind = filetype.guess(str(path))
        if kind is not None:
            mime = kind.mime or ""
            if mime == "application/pdf":
                return PdfSource(path)
            if mime.startswith("image/"):
                return ImageSource(path)
            if mime == "application/epub+zip":
                return EpubSource(path)
            if "officedocument.wordprocessing" in mime:
                return DocxSource(path)
            if "officedocument.spreadsheet" in mime:
                return ExcelSource(path)
            if "officedocument.presentation" in mime:
                return PptxSource(path)
            if mime == "text/plain" or mime == "text/csv":
                return TxtSource(path)
    except Exception:
        pass  # filetype may not be installed — fall through

    raise ConfigError(
        f"Unsupported file type for '{path.name}' (extension '{ext}'). "
        f"Supported: {sorted(set(_EXTENSION_MAP.keys()))}"
    )
