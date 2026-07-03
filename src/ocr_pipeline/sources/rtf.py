"""RTF document source — legacy word processing format.

Uses ``striprtf`` to extract plain text from RTF files.
A single file is a 1-page document.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class RtfSource(DocumentSource):
    """Document source for Rich Text Format files (``.rtf``).

    Strips RTF control codes to produce plain text via ``striprtf``.
    """

    _text_cache: str | None = None

    @property
    def source_format(self) -> str:
        return "rtf"

    @property
    def source_mimetype(self) -> str:
        return "application/rtf"

    @property
    def page_count(self) -> int:
        return 1

    def _read_text(self) -> str:
        if self._text_cache is not None:
            return self._text_cache

        try:
            from striprtf.striprtf import rtf_to_text

            raw = self.path.read_text(encoding="utf-8", errors="replace")
            self._text_cache = rtf_to_text(raw)
        except Exception:
            # Fallback: read raw
            self._text_cache = self.path.read_text(encoding="utf-8", errors="replace")

        return self._text_cache

    def extract_metadata(self) -> MetadataResult:
        _text = self._read_text()
        st = self.path.stat()

        return MetadataResult(
            document_type="document",
            extraction_method="rtf-stripping",
            source_info=SourceInfo(
                format="rtf",
                page_count=1,
                mimetype="application/rtf",
                extra={"file_size_bytes": st.st_size},
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("RtfSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text = self._read_text()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
