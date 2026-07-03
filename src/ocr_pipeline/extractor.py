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


def extract_page_images(pdf_path: Path, page_index: int, output_dir: Path) -> list[Path]:
    """Extract embedded images from a PDF page and save them to *output_dir*.

    Uses PyMuPDF (fitz) to enumerate and extract embedded images from the
    specified page.  Images are saved as individual files and the returned
    list of :class:`Path` objects points to the saved files.

    Args:
        pdf_path: Path to the source PDF.
        page_index: 0-based page number.
        output_dir: Directory where images are saved.

    Returns:
        List of paths to the saved image files (may be empty).

    Edge cases handled:
        * Duplicate images (same image referenced multiple times on a page)
          are detected and skipped after the first extraction.
        * Images smaller than 100 bytes are skipped.
        * Invalid or missing xrefs are logged and skipped gracefully.
    """
    saved: list[Path] = []
    seen_xrefs: set[int] = set()
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    try:
        page_count = len(doc)
        if page_index < 0 or page_index >= page_count:
            logger.warning(
                "Page index %d out of range for %s (0-%d)",
                page_index,
                pdf_path.name,
                page_count - 1,
            )
            return saved

        page = doc[page_index]
        image_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            if xref in seen_xrefs:
                logger.debug("Skipping duplicate image xref %d on page %d", xref, page_index + 1)
                continue
            seen_xrefs.add(xref)

            try:
                base_image = doc.extract_image(xref)
            except Exception:
                logger.debug(
                    "Failed to extract image xref %d from %s page %d",
                    xref,
                    pdf_path.name,
                    page_index + 1,
                )
                continue

            img_bytes = base_image.get("image")
            if not img_bytes or len(img_bytes) < 100:
                logger.debug(
                    "Skipping tiny/invalid image xref %d (%d bytes)", xref, len(img_bytes or b"")
                )
                continue

            ext = base_image.get("ext", "png")
            # Normalise extension (fitz sometimes returns "jpeg" vs "jpg")
            ext = ext.lower().lstrip(".")
            if ext == "jpeg":
                ext = "jpg"

            out_path = output_dir / f"img_{page_index + 1:04d}_{img_idx + 1:03d}.{ext}"
            out_path.write_bytes(img_bytes)
            saved.append(out_path)

            logger.debug(
                "Extracted image %d xref %d from %s page %d -> %s",
                img_idx + 1,
                xref,
                pdf_path.name,
                page_index + 1,
                out_path,
            )
    finally:
        doc.close()

    return saved
