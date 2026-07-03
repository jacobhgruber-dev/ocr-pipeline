"""CSV / TSV document source — structured tabular data.

Uses ``clevercsv`` for automatic dialect detection.  The entire table
is rendered as a single markdown table page.
"""

from __future__ import annotations

import logging
from pathlib import Path


from .base import DocumentSource

logger = logging.getLogger(__name__)


class CsvSource(DocumentSource):
    """Document source for CSV and TSV files.

    A single spreadsheet file is a 1-page document output as a markdown
    table.  Text extraction returns the table in markdown format.
    Rendering is not supported.
    """

    _rows_cache: list[list[str]] | None = None

    @property
    def source_format(self) -> str:
        return "csv"

    @property
    def source_mimetype(self) -> str:
        ext = self.path.suffix.lower()
        if ext in (".tsv", ".tab"):
            return "text/tab-separated-values"
        return "text/csv"

    @property
    def page_count(self) -> int:
        return 1

    def _load_rows(self) -> list[list[str]]:
        """Parse the CSV/TSV file, caching results."""
        if self._rows_cache is not None:
            return self._rows_cache

        import clevercsv as ccsv

        # Read raw bytes for sniffing, detect encoding separately
        raw = self.path.read_bytes()
        dialect = ccsv.Sniffer().sniff(raw.decode("utf-8", errors="replace"))

        # Detect encoding via charset-normalizer fallback
        encoding = "utf-8"
        try:
            from charset_normalizer import from_bytes

            results = from_bytes(raw)
            if results:
                best = results.best()
                if best and best.encoding:
                    encoding = best.encoding
        except Exception:
            pass

        text = raw.decode(encoding, errors="replace")
        rows = list(ccsv.reader(text.splitlines(), dialect=dialect))
        self._rows_cache = rows
        return rows

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError(
            "CsvSource.render_page not supported — convert to image before OCR."
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        rows = self._load_rows()
        if not rows:
            return "", None

        # Build markdown table
        lines: list[str] = []
        header = rows[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")
        for row in rows[1:]:
            padded = row + [""] * (len(header) - len(row))
            lines.append("| " + " | ".join(padded[: len(header)]) + " |")

        text = "\n".join(lines)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
