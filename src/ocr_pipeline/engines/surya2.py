from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from .base import with_api_retry
from ..models import Block, EngineName, EngineOutput

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
                if (candidate / "bin" / "python").exists():
                    venv_path = candidate
                    break
        if venv_path is None:
            raise ValueError(
                "No venv with surya-ocr found. Install: uv add surya-ocr (or pip install surya-ocr)"
            )
        self.venv_path = Path(venv_path)
        self._python = self.venv_path / "bin" / "python"

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
                block_lines.append(line.text or "")

        block_text = "\\n".join(block_lines) if block_lines else ""
        confidence = float(lbox.confidence) if lbox.confidence else 0.0

        blocks.append({{
            "type": _map_label(lb_label),
            "text": block_text,
            "bbox": list(lb_bbox) if lb_bbox else None,
            "confidence": confidence,
            "children": [],
        }})

    # --- Fallback: if no layout blocks, emit text lines directly --------------
    if not blocks:
        for line in ocr_result.text_lines:
            line_poly = line.polygon
            if line_poly and len(line_poly) >= 4:
                xs = [p[0] for p in line_poly]
                ys = [p[1] for p in line_poly]
                bbox = [min(xs), min(ys), max(xs), max(ys)]
            else:
                bbox = None
            blocks.append({{
                "type": "text",
                "text": line.text or "",
                "bbox": bbox,
                "confidence": float(line.confidence) if line.confidence else 0.0,
                "children": [],
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
        if not self.venv_path.exists():
            return False
        if not self._python.exists():
            return False

        check_script = (
            "import surya.foundation, surya.detection, surya.recognition, surya.layout; print('ok')"
        )
        try:
            result = subprocess.run(
                [str(self._python), "-c", check_script],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ},
            )
            return result.returncode == 0 and "ok" in result.stdout
        except Exception:
            return False
