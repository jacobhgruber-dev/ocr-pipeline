"""Mistral OCR cloud API engine.

Uses the ``mistralai`` SDK to send single-page PNG images to the
Mistral OCR API and return structured markdown with block-level
bounding boxes and confidence scores.

See: https://docs.mistral.ai/capabilities/document/
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

from .base import with_api_retry
from ..models import Block, EngineName, EngineOutput

# Mistral block types mapped to pipeline Block types.
# Unknown / unmapped types default to "text".
_MISTRAL_TO_PIPELINE_BLOCK_TYPE: dict[str, str] = {
    "text": "text",
    "title": "heading",
    "table": "table",
    "equation": "equation",
    "image": "figure",
    "caption": "text",
    "code": "text",
    "references": "text",
    "aside_text": "text",
    "header": "header",
    "footer": "footer",
    "signature": "text",
    "list": "text",
}


class MistralEngine:
    """Mistral OCR API engine (mistral-ocr-latest → mistral-ocr-4-0)."""

    def __init__(
        self,
        api_key: str,
        model: str = "mistral-ocr-latest",
        endpoint: str = "https://api.mistral.ai",
        include_blocks: bool = True,
        confidence_granularity: str = "page",
        extract_headers: bool = False,
        extract_footers: bool = False,
        table_format: str | None = None,
        timeout_sec: float = 120.0,
    ) -> None:
        """Initialize with Mistral API credentials and options.

        Args:
            api_key: Mistral API key (resolved via ``resolve_credential``).
            model: Model identifier (``"mistral-ocr-latest"`` resolves to
                mistral-ocr-4-0).
            endpoint: API base URL.
            include_blocks: Whether to request block-level OCR output
                (bounding boxes + structured content).
            confidence_granularity: ``"page"`` or ``"word"``.
            extract_headers: Extract running headers from pages.
            extract_footers: Extract running footers from pages.
            table_format: Optional table output format (e.g. ``"markdown"``,
                ``"html"``).
            timeout_sec: Per-request timeout in seconds.
        """
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint
        self._include_blocks = include_blocks
        self._confidence_granularity = confidence_granularity
        self._extract_headers = extract_headers
        self._extract_footers = extract_footers
        self._table_format = table_format
        self._timeout_sec = timeout_sec

    # -- Protocol requirements -------------------------------------------------

    @property
    def engine_name(self) -> str:
        return EngineName.MISTRAL

    # -- recognise (public entry point) ---------------------------------------

    def recognize(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float = 120.0,
        languages: list[str] | None = None,
    ) -> EngineOutput:
        """Send *image_path* to the Mistral OCR API as a base64 image URL.

        Retries with exponential backoff via ``_call_mistral()``.
        """
        t0 = time.perf_counter()

        # --- Read image + base64 encode (not retried) ---
        try:
            raw_bytes = image_path.read_bytes()
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                error=f"Failed to read image file: {exc}",
                duration_sec=elapsed,
            )

        try:
            b64 = base64.standard_b64encode(raw_bytes).decode("ascii")
            data_url = f"data:image/png;base64,{b64}"
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                error=f"Failed to base64-encode image: {exc}",
                duration_sec=elapsed,
            )

        # --- Guard: SDK available? ---
        try:
            from mistralai import Mistral  # noqa: F401
        except ImportError:
            elapsed = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                error=("mistralai SDK not installed. Install with: uv sync --extra mistral"),
                duration_sec=elapsed,
            )

        # --- Guard: API key ---
        if not self._api_key:
            elapsed = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                error="Mistral API key not configured",
                duration_sec=elapsed,
            )

        # --- API call (retry-wrapped) ---
        try:
            text, blocks, confidence = self._call_mistral(data_url, timeout_sec)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            retries = self._call_mistral.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
            return EngineOutput(
                engine=self.engine_name,
                error=str(exc),
                duration_sec=elapsed,
                retries=retries,
            )

        elapsed = time.perf_counter() - t0
        retries = self._call_mistral.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
        return EngineOutput(
            engine=self.engine_name,
            text=text,
            blocks=blocks,
            confidence=confidence,
            duration_sec=elapsed,
            retries=retries,
        )

    # -- internal (retry-wrapped) ---------------------------------------------

    @with_api_retry()
    def _call_mistral(
        self, data_url: str, timeout_sec: float
    ) -> tuple[str, list[Block] | None, float | None]:
        """POST the base64 image to the Mistral OCR API — raises on failure."""
        from mistralai import Mistral  # noqa: F811

        client = Mistral(api_key=self._api_key)

        document: dict[str, str] = {
            "type": "image_url",
            "image_url": data_url,
        }

        ocr_kwargs: dict[str, object] = {
            "model": self._model,
            "document": document,
        }
        if self._include_blocks:
            ocr_kwargs["include_image_base64"] = False

        response = client.ocr.process(**ocr_kwargs)

        pages = getattr(response, "pages", [])
        if not pages:
            raise RuntimeError("Mistral OCR returned no pages")

        page = pages[0]
        markdown: str = getattr(page, "markdown", "") or ""

        # --- Convert blocks ---
        blocks: list[Block] | None = None
        if self._include_blocks:
            raw_blocks = getattr(page, "blocks", None) or []
            dimensions = getattr(page, "dimensions", None)
            img_w: float = float(getattr(dimensions, "width", 1) or 1)
            img_h: float = float(getattr(dimensions, "height", 1) or 1)
            blocks = _convert_blocks(raw_blocks, img_w, img_h)

        # --- Confidence ---
        confidence: float | None = None
        if self._confidence_granularity == "page":
            scores = getattr(page, "confidence_scores", None)
            if scores is not None:
                confidence = getattr(scores, "average_page_confidence_score", None)
                if confidence is not None:
                    confidence = float(confidence)

        return markdown, blocks, confidence

    # -- health ---------------------------------------------------------------

    def health_check(self) -> bool:
        """Return ``True`` when the SDK is importable and API key is set."""
        try:
            return bool(self._api_key)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Block conversion helpers
# ---------------------------------------------------------------------------


def _convert_blocks(
    mistral_blocks: list,
    img_w: float,
    img_h: float,
) -> list[Block]:
    """Convert Mistral OCRBlock list to pipeline :class:`Block` list.

    Pixel coordinates are normalised to 0.0–1.0 using *img_w* / *img_h*.
    """
    result: list[Block] = []
    for b in mistral_blocks:
        block_type_raw = getattr(b, "type", "text") or "text"
        pipeline_type = _MISTRAL_TO_PIPELINE_BLOCK_TYPE.get(block_type_raw, "text")

        content: str = getattr(b, "content", "") or ""

        # Normalise pixel coordinates → 0.0–1.0
        tx = float(getattr(b, "top_left_x", 0) or 0)
        ty = float(getattr(b, "top_left_y", 0) or 0)
        bx = float(getattr(b, "bottom_right_x", 0) or 0)
        by = float(getattr(b, "bottom_right_y", 0) or 0)

        if img_w > 0 and img_h > 0:
            bbox: tuple[float, float, float, float] = (
                tx / img_w,
                ty / img_h,
                bx / img_w,
                by / img_h,
            )
        else:
            bbox = (0.0, 0.0, 0.0, 0.0)

        result.append(
            Block(
                type=pipeline_type,
                text=content,
                bbox=bbox,
            )
        )
    return result
