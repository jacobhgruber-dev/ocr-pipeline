from __future__ import annotations

import logging
from pathlib import Path

import fitz

from .errors import RenderError

logger = logging.getLogger(__name__)

# Default text extraction flags: preserve whitespace and ligatures for
# best fidelity to the original layout.
_DEFAULT_FLAGS = fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES


def extract_page_text(
    pdf_path: Path,
    page_index: int,
    output_dir: Path,
    flags: int | None = None,
) -> tuple[str, Path]:
    """Extract text directly from a PDF page via PyMuPDF.

    Args:
        pdf_path: Path to the source PDF.
        page_index: 0-based page number.
        output_dir: Directory to save ``page_NNNN_final.md``.
        flags: PyMuPDF text extraction flags. If ``None``, defaults to
               ``TEXT_PRESERVE_WHITESPACE | TEXT_PRESERVE_LIGATURES``.

    Returns:
        (extracted_text, path_to_saved_file)

    Raises:
        RenderError: If the page text cannot be extracted.
    """
    if flags is None:
        flags = _DEFAULT_FLAGS

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise RenderError(f"Failed to open PDF: {pdf_path}") from exc

    try:
        page_count = len(doc)
        if page_index < 0 or page_index >= page_count:
            raise RenderError(
                f"Page index {page_index} out of range for {pdf_path} (0-{page_count - 1})"
            )

        page = doc[page_index]
        text = page.get_text("text", flags=flags)
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError(f"Failed to extract text from page {page_index} of {pdf_path}") from exc
    finally:
        doc.close()

    output_path = output_dir / f"page_{page_index + 1:04d}_final.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    logger.debug(
        "Extracted %d chars from %s page %d -> %s",
        len(text),
        pdf_path.name,
        page_index,
        output_path,
    )

    return text, output_path


def extract_all_pages(
    pdf_path: Path,
    page_count: int,
    output_dir: Path,
    flags: int | None = None,
) -> list[tuple[str, Path]]:
    """Extract text from all pages of a text-extractable PDF.

    Args:
        pdf_path: Path to the source PDF.
        page_count: Number of pages in the PDF.
        output_dir: Directory to save per-page markdown files.
        flags: PyMuPDF text extraction flags. If ``None``, defaults to
               ``TEXT_PRESERVE_WHITESPACE | TEXT_PRESERVE_LIGATURES``.

    Returns:
        List of ``(text, filepath)`` tuples in page order.
        Skips pages whose output file already exists.
    """
    results: list[tuple[str, Path]] = []

    for page_index in range(page_count):
        output_path = output_dir / f"page_{page_index + 1:04d}_final.md"

        if output_path.exists():
            logger.debug("Skipping existing output: %s", output_path)
            # Read back the existing text so the return value is consistent.
            existing_text = output_path.read_text(encoding="utf-8")
            results.append((existing_text, output_path))
            continue

        text, path = extract_page_text(pdf_path, page_index, output_dir, flags=flags)
        results.append((text, path))

    return results
