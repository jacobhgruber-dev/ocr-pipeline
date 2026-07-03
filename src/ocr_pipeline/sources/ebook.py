"""E-book format detection and DRM awareness.

Detects proprietary e-book formats (.azw, .azw3, .kfx, .mobi) and
flags DRM-protected files.  Text extraction is limited or unavailable
for DRM-protected files — this source provides metadata awareness only.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, RightsInfo, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

_FORMAT_INFO: dict[str, dict[str, str]] = {
    ".azw": {"format": "azw", "mime": "application/vnd.amazon.ebook", "desc": "Kindle AZW"},
    ".azw3": {"format": "azw3", "mime": "application/vnd.amazon.ebook", "desc": "Kindle AZW3"},
    ".kfx": {"format": "kfx", "mime": "application/vnd.amazon.ebook", "desc": "Kindle KFX"},
    ".mobi": {"format": "mobi", "mime": "application/x-mobipocket-ebook", "desc": "Mobipocket"},
}

_HAS_DRM_MARKER = {
    ".azw": True,
    ".azw3": True,
    ".kfx": True,
    ".mobi": False,  # Some MOBI files are DRM-free
}


class EbookSource(DocumentSource):
    """Document source for proprietary e-book formats.

    Detects Kindle/Mobipocket formats and flags DRM status.
    Text extraction is not supported for DRM-protected files.
    """

    @property
    def source_format(self) -> str:
        ext = self.path.suffix.lower()
        return _FORMAT_INFO.get(ext, {}).get("format", "ebook")

    @property
    def source_mimetype(self) -> str:
        ext = self.path.suffix.lower()
        return _FORMAT_INFO.get(ext, {}).get("mime", "application/octet-stream")

    @property
    def page_count(self) -> int:
        return 1

    def _has_drm(self) -> bool:
        """Heuristic DRM detection based on file format and content markers."""
        ext = self.path.suffix.lower()
        if ext == ".kfx":
            return True  # KFX is always DRM-wrapped
        if ext == ".azw":
            # AZW may or may not have DRM — check for encryption markers
            try:
                header = self.path.read_bytes()[:100]
                # DRM'd AZW files have an encryption header
                if b"EBOK" not in header and b"PDOC" not in header:
                    return _HAS_DRM_MARKER.get(ext, False)
            except Exception:
                pass
        return _HAS_DRM_MARKER.get(ext, False)

    def extract_metadata(self) -> MetadataResult:
        st = self.path.stat()
        has_drm = self._has_drm()
        desc = _FORMAT_INFO.get(self.path.suffix.lower(), {}).get("desc", "E-book")

        return MetadataResult(
            title=self.path.stem,
            document_type="ebook",
            extraction_method="ebook-detection",
            source_info=SourceInfo(
                format=self.source_format,
                page_count=1,
                mimetype=self.source_mimetype,
                extra={
                    "has_drm": str(has_drm),
                    "format_description": desc,
                    "file_size_bytes": st.st_size,
                    "text_extractable": str(not has_drm),
                },
            ),
            rights=RightsInfo(
                access_restrictions="DRM-protected — text extraction unavailable" if has_drm else ""
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("E-book rendering not supported — convert with Calibre first.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        if self._has_drm():
            return f"[DRM-protected {self.source_format.upper()} — unable to extract text]", None
        return f"[{self.source_format.upper()} e-book — use Calibre for text extraction]", None
