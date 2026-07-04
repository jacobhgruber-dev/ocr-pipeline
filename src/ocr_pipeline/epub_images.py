"""Image extraction from EPUB documents.

Extracts embedded images from EPUB spine items via ebooklib.
Images are saved alongside the extracted text for downstream use
(VLM description, OCR, etc.).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/bmp",
    "image/tiff",
}


def extract_epub_images(epub_path: Path, output_dir: Path) -> list[Path]:
    """Extract all embedded images from an EPUB file.

    Args:
        epub_path: Path to the EPUB file.
        output_dir: Directory to save extracted images.

    Returns:
        List of paths to saved image files.
    """
    try:
        from ebooklib import epub
    except ImportError:
        logger.debug("ebooklib not available — skipping EPUB image extraction")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    try:
        book = epub.read_epub(str(epub_path))
    except Exception:
        logger.debug("Failed to open EPUB for image extraction: %s", epub_path.name)
        return []

    for item in book.get_items():
        if item.get_type() == epub.ITEM_IMAGE:
            media_type = item.media_type or ""
            if not any(media_type.startswith(t) for t in _IMAGE_TYPES):
                media_type = _guess_type_from_name(item.get_name())
            if not media_type:
                continue

            try:
                data = item.get_content()
                if not data or len(data) < 100:
                    continue

                ext = media_type.split("/")[-1]
                if ext == "jpeg":
                    ext = "jpg"
                safe_name = item.get_name().replace("/", "_").replace("\\", "_")
                out_path = output_dir / f"{safe_name}.{ext}"
                out_path.write_bytes(data)
                saved.append(out_path)
            except Exception:
                pass

    return saved


def _guess_type_from_name(name: str) -> str:
    ext = Path(name).suffix.lower()
    _map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    return _map.get(ext, "")
