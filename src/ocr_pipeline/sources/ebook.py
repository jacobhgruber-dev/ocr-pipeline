"""E-book format detection, DRM awareness, and Calibre conversion.

Detects proprietary e-book formats (.azw, .azw3, .kfx, .mobi) and
flags DRM-protected files.  For DRM-free files, attempts text extraction
via Calibre's ``ebook-convert`` CLI tool.

DRM detection strategies:
- AZW/AZW3: check for EBOK/PDOC markers in file header (DRM-free = these appear)
- MOBI: check header for TEXT record at offset (PalmDOC header)
- EPUB: check ZIP container for encryption.xml (Adobe DRM)
- KFX: always DRM-wrapped at the container level
"""

from __future__ import annotations

import logging
import shutil
import subprocess
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

# Byte markers for DRM detection
_MOBI_MAGIC = b"BOOKMOBI"
_PALMDOC_MAGIC = b"TEXtREAd"
_KF8_MAGIC = b"BLOCKS1\x00\x00\x00\x00"


def _check_calibre() -> bool:
    """Check if Calibre's ebook-convert is available."""
    return shutil.which("ebook-convert") is not None


def _check_dedrm() -> bool:
    """Check if Calibre DeDRM plugin is installed."""
    import os

    paths = [
        os.path.expanduser("~/Library/Preferences/calibre/plugins"),  # macOS
        os.path.expanduser("~/.config/calibre/plugins"),  # Linux
        os.path.expanduser("~/AppData/Roaming/calibre/plugins"),  # Windows
    ]
    # Also check APPDATA env var for non-standard Windows installs
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(os.path.join(appdata, "calibre", "plugins"))

    for path in paths:
        try:
            if os.path.isdir(path):
                contents = os.listdir(path)
                if any("DeDRM" in f for f in contents):
                    return True
        except OSError:
            continue
    return False


class EbookSource(DocumentSource):
    """Document source for proprietary e-book formats.

    Detects Kindle/Mobipocket formats and flags DRM status.  Uses
    Calibre's ``ebook-convert`` for text extraction from DRM-free files.
    """

    _drm_cache: bool | None = None

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

    def has_drm(self) -> bool:
        """Check if the e-book file is DRM-protected."""
        if self._drm_cache is not None:
            return self._drm_cache

        ext = self.path.suffix.lower()

        # KFX is always DRM-wrapped at the container level
        if ext == ".kfx":
            self._drm_cache = True
            return True

        # EPUB is handled by EpubSource; delegation documented here.

        # AZW/AZW3: check header markers
        if ext in (".azw", ".azw3"):
            try:
                header = self.path.read_bytes()[:200]
                # DRM-free AZW files have EBOK or PDOC markers visible
                # DRM'd files have these markers encrypted/obscured
                if b"EBOK" in header or b"PDOC" in header:
                    self._drm_cache = False
                    return False
                # Check for MOBI header (some DRM-free AZW files)
                if _MOBI_MAGIC in header:
                    self._drm_cache = False
                    return False
                self._drm_cache = True
                return True
            except Exception:
                pass

        # MOBI: check for PalmDOC text record marker
        if ext == ".mobi":
            try:
                header = self.path.read_bytes()[:200]
                if _MOBI_MAGIC in header or _PALMDOC_MAGIC in header:
                    self._drm_cache = False
                    return False
                # Absence of markers doesn't guarantee DRM for MOBI
                self._drm_cache = False  # Default: assume DRM-free for MOBI
                return False
            except Exception:
                pass

        self._drm_cache = False
        return False

    def _extract_via_calibre(self, output_dir: Path) -> str:
        """Convert e-book to plain text using Calibre's ebook-convert."""
        txt_path = output_dir / "converted.txt"
        try:
            result = subprocess.run(
                [
                    "ebook-convert",
                    str(self.path),
                    str(txt_path),
                    "--to",
                    "txt",
                    "--max-toc-links",
                    "0",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0 and txt_path.exists():
                return txt_path.read_text(encoding="utf-8", errors="replace")
            logger.warning("ebook-convert failed: %s", result.stderr[:200])
        except FileNotFoundError:
            logger.debug("ebook-convert (Calibre) not installed — skipping text extraction")
        except Exception as exc:
            logger.warning("ebook-convert error: %s", exc)
        txt_path.unlink(missing_ok=True)
        return ""

    def extract_metadata(self) -> MetadataResult:
        st = self.path.stat()
        has_drm = self.has_drm()
        desc = _FORMAT_INFO.get(self.path.suffix.lower(), {}).get("desc", "E-book")
        calibre_available = _check_calibre()
        dedrm_available = _check_dedrm()
        extractable = not has_drm and calibre_available

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
                    "text_extractable": str(extractable),
                    "calibre_available": str(calibre_available),
                    "dedrm_plugin": str(dedrm_available),
                },
            ),
            rights=RightsInfo(
                access_restrictions="DRM-protected — text extraction unavailable"
                if has_drm
                else (
                    ""
                    if calibre_available
                    else "Calibre not installed — text extraction unavailable"
                )
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("E-book rendering not supported — convert with Calibre first.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"

        if self.has_drm():
            text = f"[DRM-protected {self.source_format.upper()} — unable to extract text]"
            out_path.write_text(text, encoding="utf-8")
            return text, out_path

        # Try Calibre conversion for DRM-free files
        text = self._extract_via_calibre(output_dir)
        if text.strip():
            out_path.write_text(text, encoding="utf-8")
            return text, out_path

        # No Calibre available — provide guidance
        text = (
            f"[{self.source_format.upper()} e-book — text extraction requires Calibre]\n\n"
            "Install Calibre (https://calibre-ebook.com) to enable text extraction "
            "from DRM-free e-book formats. Once installed, this pipeline will use "
            "`ebook-convert` to extract text automatically."
        )
        out_path.write_text(text, encoding="utf-8")
        return text, out_path
