"""Image extraction from DOCX documents.

Extracts embedded images from DOCX files via python-docx relationship
iteration.  Images are saved alongside extracted text.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_docx_images(docx_path: Path, output_dir: Path) -> list[Path]:
    """Extract all embedded images from a DOCX file.

    Args:
        docx_path: Path to the DOCX file.
        output_dir: Directory to save extracted images.

    Returns:
        List of paths to saved image files.
    """
    try:
        from docx import Document
    except ImportError:
        logger.debug("python-docx not available — skipping DOCX image extraction")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    try:
        doc = Document(str(docx_path))
    except Exception:
        logger.debug("Failed to open DOCX for image extraction: %s", docx_path.name)
        return []

    # Image relationships are stored in the document part
    image_count = 0
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                image = rel.target_part
                data = image.blob
                if not data or len(data) < 100:
                    continue

                ext = image.content_type.split("/")[-1]
                if ext == "jpeg":
                    ext = "jpg"
                image_count += 1
                out_path = output_dir / f"img_{image_count:03d}.{ext}"
                out_path.write_bytes(data)
                saved.append(out_path)
            except Exception:
                pass

    return saved
