"""TrOCR handwriting recognition engine.

Wraps Microsoft's TrOCR model as an OcrEngine-compatible class.
Handles text-line detection via Surya or EasyOCR, then runs TrOCR
on each detected line.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.models import Block, EngineName, EngineOutput

from .base import OcrEngine

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "microsoft/trocr-base-handwritten"


class TrocrEngine(OcrEngine):
    """Handwriting OCR engine using Microsoft TrOCR.

    TrOCR (Transformer-based OCR) achieves 3.42% CER on the IAM
    handwriting benchmark.  It uses a Vision Transformer encoder
    and a RoBERTa decoder — pure Transformer, no CNN.

    CPU inference is slow (~2-5 seconds per text line).  GPU
    recommended for batch processing.
    """

    @property
    def engine_name(self) -> EngineName:
        return EngineName.TROCR

    def health_check(self) -> bool:
        """Return True if torch + transformers are importable."""
        try:
            import importlib.util

            for mod in ("torch", "transformers"):
                if importlib.util.find_spec(mod) is None:
                    return False
            return True
        except Exception:
            return False

    def recognize(
        self,
        image_path: Path,
        languages: list[str] | None = None,
        dpi: int = 300,
    ) -> EngineOutput:
        t0 = __import__("time").perf_counter()

        try:
            from ocr_pipeline.handwriting import recognize_handwriting

            model = getattr(self, "_trocr_model", None) or _DEFAULT_MODEL
            full_text, line_results = recognize_handwriting(
                image_path, model_name=model, detector="easyocr", quantize=False
            )
        except Exception as exc:
            logger.warning("TrOCR recognition failed: %s", exc)
            return EngineOutput(
                engine="trocr",
                text="",
                blocks=[],
                confidence=0.0,
                cost=0.0,
                metadata={"error": str(exc)},
            )

        elapsed = __import__("time").perf_counter() - t0

        # Build blocks from line results
        blocks: list[Block] = []
        for i, line in enumerate(line_results):
            blocks.append(
                Block(
                    block_id=f"trocr_line_{i}",
                    type="text",
                    text=line["text"],
                    bbox=line.get("bbox"),
                    confidence=min(line.get("confidence", 0.0), 1.0),
                )
            )

        return EngineOutput(
            engine="trocr",
            text=full_text,
            blocks=blocks,
            confidence=(
                sum(b.confidence for b in blocks) / len(blocks) if blocks else 0.0
            ),
            cost=0.0,  # Free — local model, no API
            metadata={
                "model": model,
                "lines_detected": len(line_results),
                "elapsed_sec": round(elapsed, 1),
            },
        )
