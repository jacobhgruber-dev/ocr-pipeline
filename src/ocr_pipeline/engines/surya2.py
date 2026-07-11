from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .base import with_api_retry
from .base import _get_venv_python
from ..models import Block, EngineName, EngineOutput

logger = logging.getLogger(__name__)

# -- label mapping -----------------------------------------------------------

_SURYA_LABEL_MAP: dict[str, str] = {
    "SectionHeader": "heading",
    "Text": "text",
    "Table": "table",
    "Picture": "figure",
    "Figure": "figure",
    "Footnote": "footer",
    "PageHeader": "header",
    "PageFooter": "footer",
    "Caption": "text",
    "ListItem": "text",
    "Equation": "equation",
    "Code": "text",
    "TableOfContents": "text",
    "Form": "text",
}


def _map_label(raw: str) -> str:
    return _SURYA_LABEL_MAP.get(raw, "text")


class Surya2Engine:
    """Surya 2 OCR engine — 650M VLM for OCR + layout + table detection.

    Runs as a **subprocess** to avoid dependency conflicts.  Requires
    ``surya-ocr`` installed in a virtual environment.  On first run
    models are downloaded automatically (~2 GB total).

    Install::

        uv add surya-ocr   # or pip install surya-ocr

    Models are auto-downloaded on first use from HuggingFace (S3).
    """

    def __init__(self, venv_path: Path | None = None) -> None:
        """*venv_path*: Path to Python venv with ``surya-ocr`` installed.

        When ``None``, auto-discovers ``.venv-marker`` or ``.venv-surya``
        relative to the project root.
        """
        if venv_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
            for candidate_name in (".venv-marker", ".venv-surya"):
                candidate = project_root / candidate_name
                if _get_venv_python(candidate).exists():
                    venv_path = candidate
                    break
        if venv_path is None:
            # Fall back to current Python (e.g., surya installed in same venv)
            import sys as _sys

            venv_path = Path(_sys.executable).parent.parent  # venv root
        self.venv_path = Path(venv_path)
        self._python = _get_venv_python(self.venv_path)
        if not self._python.exists():
            import sys as _sys2

            self._python = Path(_sys2.executable)

    # -- public API -----------------------------------------------------------

    @property
    def engine_name(self) -> str:
        return EngineName.SURYA2

    def recognize(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float = 300.0,
        languages: list[str] | None = None,
        pdf_path: Path | None = None,
    ) -> EngineOutput:
        """Run Surya 2 OCR on a page image.

        When *pdf_path* is provided, the page is extracted directly
        from the PDF at 300 DPI inside the subprocess.  Otherwise
        *image_path* is used as-is.
        """
        t0 = time.perf_counter()

        if not image_path.exists() and pdf_path is None:
            return EngineOutput(
                engine=self.engine_name,
                error=f"Image not found: {image_path}",
            )
        if not self._python.exists():
            return EngineOutput(
                engine=self.engine_name,
                error=f"Python not found at {self._python}",
            )

        try:
            output = self._run_surya(image_path, page_index, timeout_sec, pdf_path, languages)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            retries = self._run_surya.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
            return EngineOutput(
                engine=self.engine_name,
                error=str(exc),
                duration_sec=elapsed,
                retries=retries,
            )

        elapsed = time.perf_counter() - t0
        retries = self._run_surya.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
        blocks = None
        if output.get("blocks"):
            blocks = [Block.from_dict(b) for b in output["blocks"]]
        return EngineOutput(
            engine=self.engine_name,
            text=output.get("text", ""),
            duration_sec=elapsed,
            retries=retries,
            blocks=blocks,
        )

    # -- subprocess (retry-wrapped) -------------------------------------------

    @with_api_retry(extra_retry_on=(subprocess.TimeoutExpired,))
    def _run_surya(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float,
        pdf_path: Path | None,
        languages: list[str] | None = None,
    ) -> dict:
        """Invoke Surya 2 via subprocess — raises on failure so tenacity retries."""

        label_map_entries = ",\n        ".join(
            f"{json.dumps(k)}: {json.dumps(v)}" for k, v in _SURYA_LABEL_MAP.items()
        )

        # Build the subprocess script --------------------------------------------------
        script = f"""\
import json, sys, os

_LABEL_MAP = {{
    {label_map_entries}
}}

def _map_label(raw: str) -> str:
    return _LABEL_MAP.get(raw, "text")

try:
    from PIL import Image

    # --- Determine input image -------------------------------------------------
    pdf_path = {json.dumps(str(pdf_path)) if pdf_path else "None"}
    page_num = {page_index}
    img_path = None

    if pdf_path and os.path.exists(pdf_path):
        import fitz
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        import tempfile as _tmp
        with _tmp.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(pix.tobytes("png"))
            img_path = f.name
        doc.close()
    else:
        img_path = {json.dumps(str(image_path))}

    # --- Load models ----------------------------------------------------------
    from surya.foundation import FoundationPredictor
    from surya.detection import DetectionPredictor
    from surya.recognition import RecognitionPredictor
    from surya.layout import LayoutPredictor

    foundation = FoundationPredictor()
    det = DetectionPredictor()
    rec = RecognitionPredictor(foundation)
    layout = LayoutPredictor(foundation)

    # --- Load image -----------------------------------------------------------
    image = Image.open(img_path).convert("RGB")

    # --- Run OCR (detect + recognize) -----------------------------------------
    from surya.common.surya.schema import TaskNames
    task_names = [TaskNames.ocr_with_boxes]
    ocr_results = rec(
        [image],
        task_names=task_names,
        det_predictor=det,
        highres_images=None,
    )

    ocr_result = ocr_results[0]

    # --- Run layout analysis --------------------------------------------------
    layout_results = layout([image])
    layout_result = layout_results[0]

    # --- Build blocks from layout boxes + OCR text ----------------------------
    # For each layout box, find OCR text lines that overlap and combine them.
    layout_boxes = sorted(layout_result.bboxes, key=lambda b: b.position)

    blocks = []
    for lbox in layout_boxes:
        lb_bbox = lbox.bbox  # [x0, y0, x1, y1]
        lb_label = lbox.label or "Text"

        # Collect text lines whose bbox overlaps this layout box
        block_lines = []
        block_word_dicts = []
        for line in ocr_result.text_lines:
            line_poly = line.polygon
            if not line_poly or len(line_poly) < 4:
                continue
            # line_poly is [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]
            xs = [p[0] for p in line_poly]
            ys = [p[1] for p in line_poly]
            lx0, ly0, lx1, ly1 = min(xs), min(ys), max(xs), max(ys)

            # Check overlap
            ox0 = max(lb_bbox[0], lx0)
            oy0 = max(lb_bbox[1], ly0)
            ox1 = min(lb_bbox[2], lx1)
            oy1 = min(lb_bbox[3], ly1)
            if ox0 < ox1 and oy0 < oy1:
                line_text = line.text or ""
                block_lines.append(line_text)
                # Compute word-level bboxes by splitting line width evenly
                stripped = line_text.strip()
                if stripped:
                    words = stripped.split()
                    num_words = len(words)
                    line_width = lx1 - lx0
                    word_width = line_width / num_words
                    ln_conf = float(line.confidence) if line.confidence else 0.0
                    for wi, w in enumerate(words):
                        wx0 = lx0 + wi * word_width
                        wx1 = lx0 + (wi + 1) * word_width
                        block_word_dicts.append({{
                            "text": w,
                            "bbox": [wx0, ly0, wx1, ly1],
                            "confidence": ln_conf,
                        }})

        block_text = "\\n".join(block_lines) if block_lines else ""
        confidence = float(lbox.confidence) if lbox.confidence else 0.0

        blocks.append({{
            "type": _map_label(lb_label),
            "text": block_text,
            "bbox": list(lb_bbox) if lb_bbox else None,
            "confidence": confidence,
            "children": [],
            "words": block_word_dicts,
        }})

    # --- Fallback: if no layout blocks, emit text lines directly --------------
    if not blocks:
        for line in ocr_result.text_lines:
            line_poly = line.polygon
            if line_poly and len(line_poly) >= 4:
                xs = [p[0] for p in line_poly]
                ys = [p[1] for p in line_poly]
                lx0, ly0, lx1, ly1 = min(xs), min(ys), max(xs), max(ys)
                bbox = [lx0, ly0, lx1, ly1]
            else:
                bbox = None

            # Compute word-level bboxes by splitting line width evenly
            word_dicts = []
            line_text = line.text or ""
            stripped = line_text.strip()
            if stripped and bbox is not None:
                words = stripped.split()
                num_words = len(words)
                line_width = lx1 - lx0
                word_width = line_width / num_words
                ln_conf = float(line.confidence) if line.confidence else 0.0
                for wi, w in enumerate(words):
                    wx0 = lx0 + wi * word_width
                    wx1 = lx0 + (wi + 1) * word_width
                    word_dicts.append({{
                        "text": w,
                        "bbox": [wx0, ly0, wx1, ly1],
                        "confidence": ln_conf,
                    }})

            blocks.append({{
                "type": "text",
                "text": line.text or "",
                "bbox": bbox,
                "confidence": float(line.confidence) if line.confidence else 0.0,
                "children": [],
                "words": word_dicts,
            }})

    # --- Full text ------------------------------------------------------------
    full_text = "\\n".join(line.text or "" for line in ocr_result.text_lines)

    print(json.dumps({{"text": full_text, "blocks": blocks}}))

    # --- Cleanup temp file ----------------------------------------------------
    if pdf_path and img_path and img_path != str({json.dumps(str(image_path))}):
        try:
            os.unlink(img_path)
        except OSError:
            pass

except Exception as e:
    import traceback
    print(json.dumps({{"error": str(e), "traceback": traceback.format_exc()}}))
    sys.exit(1)
"""

        script_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(script)
                script_path = Path(f.name)

            result = subprocess.run(
                [str(self._python), str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env={**os.environ},
            )

            stdout = result.stdout.strip()
            if result.returncode != 0 and not stdout:
                stderr = result.stderr.strip() or "<no stderr>"
                raise RuntimeError(
                    f"Surya 2 subprocess failed (exit {result.returncode}): {stderr}"
                )

            data = json.loads(stdout)

            if "error" in data:
                traceback_info = data.get("traceback", "")
                msg = data["error"]
                if traceback_info:
                    msg = f"{msg}\n{traceback_info}"
                raise RuntimeError(msg)

            text = data.get("text", "")
            if not text.strip() and not data.get("blocks"):
                raise RuntimeError("Surya 2 returned empty text and no blocks")

            return data

        finally:
            if script_path is not None:
                try:
                    script_path.unlink()
                except OSError:
                    pass

    # -- health ---------------------------------------------------------------

    def health_check(self) -> bool:
        """Check that the venv exists and surya is importable."""
        if not self._python.exists():
            return False

        # Use lightweight find_spec to avoid triggering model downloads
        check_script = (
            "import importlib.util; "
            "ok = all(importlib.util.find_spec(m) is not None "
            "for m in ('surya.foundation', 'surya.detection', 'surya.recognition', 'surya.layout')); "
            "print('ok' if ok else 'missing')"
        )
        try:
            result = subprocess.run(
                [str(self._python), "-c", check_script],
                capture_output=True,
                text=True,
                timeout=15,
                env={**os.environ},
            )
            return result.returncode == 0 and "ok" in result.stdout
        except Exception:
            return False


def extract_tables_from_image(
    image_path: Path,
    detection_results: Any = None,
) -> list[dict]:
    """Extract table structure from a rendered page image using Surya 2.

    Uses Surya's ``TableRecPredictor`` to detect and structurally parse
    tables (rows, columns, cells) from a page image.

    Args:
        image_path: Path to the rendered page image (PNG or JPEG).
        detection_results: Optional Surya layout detection results with
            bounding boxes.  When provided, table regions are cropped from
            the image before table recognition (faster and more accurate).
            When ``None``, the entire image is processed.

    Returns:
        List of dicts, one per detected table, with keys:

        * ``rows`` — list of row y-positions (floats)
        * ``cols`` — list of column x-positions (floats)
        * ``cells`` — list of cell dicts, each with ``text``, ``row``,
          ``col``, ``rowspan``, ``colspan``, ``bbox`` (list of 4 floats)
        * ``html_table`` — basic HTML ``<table>`` string

    If ``TableRecPredictor`` is not available (older surya-ocr version or
    import error), returns an empty list and logs a debug message.
    """
    try:
        from surya.table_rec import TableRecPredictor  # noqa: PLC0415
    except ImportError:
        logger.debug("TableRecPredictor not available in this surya-ocr version")
        return []

    from PIL import Image  # noqa: PLC0415

    img = Image.open(image_path).convert("RGB")
    results: list[dict] = []

    predictor = TableRecPredictor()

    if detection_results is not None and hasattr(detection_results, "bboxes"):
        # Crop each table bbox and run table recognition on the crop
        table_bboxes = []
        for bbox_info in detection_results.bboxes:
            label = getattr(bbox_info, "label", "")
            if label and label.lower() == "table":
                bbox = getattr(bbox_info, "bbox", None)
                if bbox and len(bbox) == 4:
                    table_bboxes.append(bbox)

        if table_bboxes:
            cropped_images = []
            for bbox in table_bboxes:
                x0, y0, x1, y1 = (int(v) for v in bbox)
                cropped = img.crop((x0, y0, x1, y1))
                cropped_images.append(cropped)

            table_results = predictor(cropped_images)

            for t_result, t_bbox in zip(table_results, table_bboxes):
                results.append(_format_table_result(t_result, t_bbox))
            return results

    # Fallback: run on full image
    table_results = predictor([img])
    for t_result in table_results:
        results.append(_format_table_result(t_result, None))
    return results


def _format_table_result(t_result: Any, crop_bbox: list | None) -> dict:
    """Convert a Surya TableRecResult into a plain dict."""
    cells = []
    for cell in getattr(t_result, "cells", []):
        cell_bbox = getattr(cell, "bbox", None)
        if cell_bbox is not None:
            cell_bbox = list(cell_bbox)
        cells.append(
            {
                "text": getattr(cell, "text", "") or "",
                "row": getattr(cell, "row", 0),
                "col": getattr(cell, "col", 0),
                "rowspan": getattr(cell, "rowspan", 1),
                "colspan": getattr(cell, "colspan", 1),
                "bbox": cell_bbox,
            }
        )

    rows = getattr(t_result, "rows", [])
    if hasattr(rows, "tolist"):
        rows = rows.tolist()
    cols = getattr(t_result, "cols", [])
    if hasattr(cols, "tolist"):
        cols = cols.tolist()

    html_table = _build_html_table(cells)

    return {
        "rows": list(rows) if rows else [],
        "cols": list(cols) if cols else [],
        "cells": cells,
        "html_table": html_table,
    }


def _build_html_table(cells: list[dict]) -> str:
    """Build a basic HTML table string from cell dicts."""
    if not cells:
        return "<table></table>"

    max_row = max(c["row"] for c in cells)
    max_col = max(c["col"] for c in cells)

    # Build a 2D grid
    grid: list[list[str]] = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]
    for cell in cells:
        r, c = cell["row"], cell["col"]
        if 0 <= r <= max_row and 0 <= c <= max_col:
            grid[r][c] = cell["text"]

    parts = ["<table>"]
    for row in grid:
        parts.append("<tr>")
        for col_val in row:
            parts.append(f"<td>{col_val}</td>")
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)
