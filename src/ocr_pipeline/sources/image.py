"""Image document source — single-page documents from raster image files.

Supported formats: PNG, JPEG, TIFF, BMP, WebP, and any format Pillow can open.
Multi-page TIFF files are supported — each frame becomes a logical page.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.errors import RenderError

from .base import DocumentSource

logger = logging.getLogger(__name__)


class ImageSource(DocumentSource):
    """Document source for raster image files.

    A single JPEG/PNG is treated as a 1-page document.  Multi-frame TIFF
    files are treated as multi-page documents (one page per frame).
    """

    has_text_extraction: bool = False
    has_rendering: bool = True

    _format: str | None = None

    @property
    def source_format(self) -> str:
        return "image"

    @property
    def source_mimetype(self) -> str:
        fmt = self._detect_format()
        _mimetypes: dict[str, str] = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "tiff": "image/tiff",
            "bmp": "image/bmp",
            "webp": "image/webp",
        }
        return _mimetypes.get(fmt, "application/octet-stream")

    def _detect_format(self) -> str:
        if self._format is not None:
            return self._format
        try:
            from PIL import Image

            with Image.open(str(self.path)) as img:
                self._format = (img.format or "").lower()
        except Exception:
            self._format = "unknown"
        return self._format

    @property
    def page_count(self) -> int:
        fmt = self._detect_format()
        if fmt == "tiff":
            return self._tiff_page_count()
        return 1

    def _tiff_page_count(self) -> int:
        try:
            from PIL import Image

            with Image.open(str(self.path)) as img:
                count = 0
                while True:
                    count += 1
                    try:
                        img.seek(count)
                    except EOFError:
                        break
                return count
        except Exception:
            return 1

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"page_{page_index + 1:04d}.png"

        if out_path.exists():
            logger.debug("Skipping %s (already exists)", out_path)
            return out_path

        try:
            from PIL import Image

            with Image.open(str(self.path)) as img:
                # Seek to frame for multi-page TIFF
                if self._detect_format() == "tiff" and page_index > 0:
                    try:
                        img.seek(page_index)
                    except EOFError:
                        raise RenderError(f"TIFF page {page_index} out of range for {self.path}")

                # Always save as PNG for OCR
                converted = img.convert("RGB")
                converted.save(str(out_path), "PNG")
            logger.info("Saved image page %d -> %s", page_index + 1, out_path)
            return out_path
        except RenderError:
            raise
        except Exception as exc:
            raise RenderError(f"Failed to render image page {page_index} of {self.path}") from exc

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        # Images have no embedded text — always fall through to OCR.
        return "", None


# Register HEIC/HEIF support if pillow-heif is installed (module-level, once at import)
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass
