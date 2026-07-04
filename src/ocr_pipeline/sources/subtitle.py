"""Subtitle document source — .srt and .vtt files.

Parses subtitle files (SRT and WebVTT) and extracts the transcript
text with timestamps removed.  Metadata includes subtitle count and
language if specified.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

_VTT_TAG = re.compile(r"<[^>]+>")


class SubtitleSource(DocumentSource):
    """Document source for subtitle files (``.srt``, ``.vtt``, ``.sbv``).

    Extracts transcript text, stripping timestamps and sequence numbers.
    A single file is a 1-page document.
    """

    _text_cache: str | None = None

    @property
    def source_format(self) -> str:
        ext = self.path.suffix.lower()
        return {".srt": "srt", ".vtt": "vtt", ".sbv": "sbv"}.get(ext, "subtitle")

    @property
    def source_mimetype(self) -> str:
        ext = self.path.suffix.lower()
        mimes = {".srt": "application/x-subrip", ".vtt": "text/vtt", ".sbv": "text/sbv"}
        return mimes.get(ext, "text/plain")

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> str:
        if self._text_cache is not None:
            return self._text_cache

        raw = self.path.read_text(encoding="utf-8", errors="replace")
        ext = self.path.suffix.lower()

        if ext == ".srt":
            # Strip sequence numbers and timestamps, keep text
            lines: list[str] = []
            for block in raw.split("\n\n"):
                block = block.strip()
                if not block:
                    continue
                parts = block.split("\n")
                text_lines = []
                for line in parts:
                    if re.match(r"^\d+$", line.strip()):
                        continue
                    if re.match(r"^\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->", line.strip()):
                        continue
                    if line.strip():
                        text_lines.append(line.strip())
                if text_lines:
                    lines.append(" ".join(text_lines))
            self._text_cache = "\n".join(lines)
        elif ext == ".vtt":
            # Strip WebVTT header, timestamps, and tags
            in_body = False
            vtt_lines: list[str] = []
            for line in raw.split("\n"):
                line = line.strip()
                if line == "":
                    in_body = True
                    continue
                if not in_body:
                    continue
                if re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->", line):
                    continue
                if line.startswith("NOTE") or line.startswith("STYLE"):
                    continue  # Skip metadata lines, stay in body
                line = _VTT_TAG.sub("", line).strip()
                if line and not line.isdigit():
                    vtt_lines.append(line)
            self._text_cache = "\n".join(vtt_lines)
        else:
            self._text_cache = raw

        return self._text_cache

    def extract_metadata(self) -> MetadataResult:
        text = self._parse()
        st = self.path.stat()
        subtitle_count = len([ln for ln in text.split("\n") if ln.strip()])

        return MetadataResult(
            document_type="subtitle",
            extraction_method="subtitle-parsing",
            source_info=SourceInfo(
                format=self.source_format,
                page_count=1,
                mimetype=self.source_mimetype,
                extra={
                    "line_count": subtitle_count,
                    "char_count": len(text),
                    "file_size_bytes": st.st_size,
                },
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("SubtitleSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
