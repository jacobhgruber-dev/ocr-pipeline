"""PDF page renderer for the OCR pipeline.

Renders individual PDF pages to high-resolution PNG images using PyMuPDF
(fitz).  All functions accept ``pathlib.Path`` objects.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .errors import RenderError

try:
    import fitz
except ImportError as exc:
    msg = "PyMuPDF (fitz) is required for PDF rendering. Install it with: pip install pymupdf"
    raise ImportError(msg) from exc

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def render_page(
    pdf_path: Path,
    page_index: int,
    output_dir: Path,
    dpi: int = 300,
    force: bool = False,
) -> Path:
    """Render a single PDF page to a high-resolution PNG using PyMuPDF.

    Args:
        pdf_path: Path to the source PDF.
        page_index: 0-based page number.
        output_dir: Directory to save the rendered image.
        dpi: Output resolution (default 300).
        force: If True, re-render even if the PNG already exists.

    Returns:
        Path to the rendered PNG file.

    The output filename is ``page_{page_index+1:04d}.png``
    (e.g., ``page_0001.png``).

    Raises:
        RenderError: If the page cannot be rendered.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"page_{page_index + 1:04d}.png"
    output_path = output_dir / filename

    if not force and output_path.exists():
        logger.debug("Skipping %s (already exists)", output_path)
        return output_path

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise RenderError(f"Failed to open PDF: {pdf_path}") from exc

    try:
        if page_index < 0 or page_index >= doc.page_count:
            doc.close()
            raise RenderError(
                f"Page index {page_index} out of range (PDF has {doc.page_count} pages)"
            )

        page = doc[page_index]

        # 72 is the PDF default DPI; scale to requested DPI.
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        pix.save(str(output_path))

        logger.info(
            "Rendered %s page %d -> %s",
            pdf_path.name,
            page_index + 1,
            output_path,
        )
        return output_path
    except Exception as exc:
        raise RenderError(f"Failed to render page {page_index} of {pdf_path}") from exc
    finally:
        doc.close()


def render_all_pages(
    pdf_path: Path,
    page_count: int,
    output_dir: Path,
    dpi: int = 300,
    force: bool = False,
) -> list[Path]:
    """Render all pages of a PDF to PNGs.

    Returns list of image paths in page order (index 0, 1, 2...).
    Skips pages whose PNG already exists (unless ``force=True``).
    """
    paths: list[Path] = []
    for i in range(page_count):
        img_path = render_page(pdf_path, i, output_dir, dpi=dpi, force=force)
        paths.append(img_path)
    return paths


def get_page_count(pdf_path: Path) -> int:
    """Return the number of pages in a PDF using PyMuPDF."""
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise RenderError(f"Failed to open PDF: {pdf_path}") from exc

    try:
        return doc.page_count
    finally:
        doc.close()
