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

    _sheet_names: list[str] | None = None
    _sheets_data: dict[str, list[list[str]]] | None = None

    @property
    def source_format(self) -> str:
        return "excel"

    @property
    def source_mimetype(self) -> str:
        ext = self.path.suffix.lower()
        if ext == ".xls":
            return "application/vnd.ms-excel"
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def _load_sheets(self) -> tuple[list[str], dict[str, list[list[str]]]]:
        """Parse the Excel file, caching sheet names and data."""
        if self._sheet_names is not None and self._sheets_data is not None:
            return self._sheet_names, self._sheets_data

        from python_calamine import CalamineWorkbook

        wb = CalamineWorkbook.from_path(str(self.path))
        self._sheet_names = list(wb.sheet_names)
        self._sheets_data = {}

        for name in self._sheet_names:
            rows = wb.get_sheet_by_name(name).to_python()
            # Convert all cells to strings
            str_rows = []
            for row in rows:
                str_rows.append([str(cell) if cell is not None else "" for cell in row])
            self._sheets_data[name] = str_rows

        return self._sheet_names, self._sheets_data

    @property
    def page_count(self) -> int:
        names, _data = self._load_sheets()
        return len(names)

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError(
            "ExcelSource.render_page not supported — convert to image before OCR."
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        names, data = self._load_sheets()
        if page_index < 0 or page_index >= len(names):
            raise RenderError(f"Excel sheet index {page_index} out of range ({len(names)} sheets)")

        sheet_name = names[page_index]
        rows = data[sheet_name]

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
