"""Excel document source — structured spreadsheet files.

Uses ``python-calamine`` for fast .xlsx/.xls reading.  Each worksheet
is treated as a logical page and output as a markdown table.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.errors import RenderError

from .base import DocumentSource

logger = logging.getLogger(__name__)


class ExcelSource(DocumentSource):
    """Document source for Excel files (.xlsx, .xls, .xlsm).

    Each worksheet is a single logical page.  Text extraction reads all
    cells and produces a markdown table.  Rendering is not supported.
    """

    _sheets: list[tuple[str, list[list[str]]]] | None = None

    @property
    def source_format(self) -> str:
        return "excel"

    @property
    def source_mimetype(self) -> str:
        ext = self.path.suffix.lower()
        if ext == ".xls":
            return "application/vnd.ms-excel"
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def _load_sheets(self) -> list[tuple[str, list[list[str]]]]:
        """Parse the Excel file, caching sheet names and data together.

        Returns a single list of ``(sheet_name, rows)`` tuples so names
        and data cannot get out of sync across calls.
        """
        if self._sheets is not None:
            return self._sheets

        from python_calamine import CalamineWorkbook

        try:
            wb = CalamineWorkbook.from_path(str(self.path))
        except Exception as exc:
            raise RenderError(f"Failed to open Excel file: {self.path}") from exc

        result: list[tuple[str, list[list[str]]]] = []
        for name in wb.sheet_names:
            rows = wb.get_sheet_by_name(name).to_python()
            # Convert all cells to strings
            str_rows: list[list[str]] = []
            for row in rows:
                str_rows.append([str(cell) if cell is not None else "" for cell in row])
            result.append((name, str_rows))

        self._sheets = result
        return result

    @property
    def page_count(self) -> int:
        try:
            return len(self._load_sheets())
        except Exception:
            return 0

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError(
            "ExcelSource.render_page not supported — convert to image before OCR."
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        sheets = self._load_sheets()
        if page_index < 0 or page_index >= len(sheets):
            raise RenderError(f"Excel sheet index {page_index} out of range ({len(sheets)} sheets)")

        sheet_name, rows = sheets[page_index]

        if not rows:
            return f"# {sheet_name}\n\n(empty sheet)", None

        # Determine column count from the widest row
        col_count = max(len(row) for row in rows) if rows else 0
        if col_count == 0:
            return f"# {sheet_name}\n\n(empty sheet)", None

        # Pad all rows to the same width
        padded = [row + [""] * (col_count - len(row)) for row in rows]

        # Build markdown table
        lines: list[str] = [f"# {sheet_name}", ""]
        lines.append("| " + " | ".join(padded[0]) + " |")
        lines.append("| " + " | ".join("---" for _ in range(col_count)) + " |")
        for row in padded[1:]:
            lines.append("| " + " | ".join(row) + " |")

        text = "\n".join(lines)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"page_{page_index + 1:04d}_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
