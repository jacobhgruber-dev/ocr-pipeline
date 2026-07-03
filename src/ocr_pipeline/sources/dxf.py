"""DXF (Drawing Exchange Format) document source — CAD files.

DXF is a text-based format used by AutoCAD and other CAD tools.
Parses sections (HEADER, TABLES, ENTITIES) and extracts text content
from MTEXT and TEXT entities.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class DxfSource(DocumentSource):
    """Document source for DXF CAD files (``.dxf``).

    Extracts text from MTEXT and TEXT entities.  Each DXF file is a
    single-page document.
    """

    _text_cache: str | None = None
    _meta_cache: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        return "dxf"

    @property
    def source_mimetype(self) -> str:
        return "application/dxf"

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> tuple[str, dict[str, str]]:
        if self._text_cache is not None and self._meta_cache is not None:
            return self._text_cache, self._meta_cache

        raw = self.path.read_text(encoding="utf-8", errors="replace")

        meta: dict[str, str] = {}
        texts: list[str] = []

        # Parse DXF group code structure (code on one line, value on next)
        lines = raw.split("\n")
        i = 0
        in_entities = False
        current_text = ""
        current_code = ""

        while i < len(lines) - 1:
            try:
                code = int(lines[i].strip())
                value = lines[i + 1].strip()
            except (ValueError, IndexError):
                i += 1
                continue

            # Section detection
            if code == 2 and value == "ENTITIES":
                in_entities = True
            elif code == 2 and value == "ENDSEC" and in_entities:
                in_entities = False

            if in_entities:
                if code == 0 and value in ("TEXT", "MTEXT", "ATTRIB"):
                    current_code = value
                    if current_text:
                        texts.append(current_text)
                        current_text = ""
                elif code == 1 and current_code:
                    current_text = value

            i += 2

        if current_text:
            texts.append(current_text)
        self._text_cache = "\n\n".join(texts)

        # Metadata from HEADER variables
        self._meta_cache = meta
        return self._text_cache, meta

    def extract_metadata(self) -> MetadataResult:
        _text, _meta = self._parse()
        st = self.path.stat()

        return MetadataResult(
            title=self.path.stem,
            document_type="cad-drawing",
            extraction_method="dxf-parsing",
            source_info=SourceInfo(
                format="dxf",
                page_count=1,
                mimetype="application/dxf",
                extra={"file_size_bytes": st.st_size},
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("DxfSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _meta = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(f"# DXF: {self.path.name}\n\n{text}", encoding="utf-8")

        return text, out_path
