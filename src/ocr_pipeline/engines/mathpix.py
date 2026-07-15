from __future__ import annotations

import json
import time
from pathlib import Path

from .base import with_api_retry
from ..models import EngineName, EngineOutput
from ocr_pipeline.credentials import resolve_credential


class MathpixEngine:
    """Mathpix OCR API engine (v3/text endpoint)."""

    def __init__(
        self,
        app_id: str | None = None,
        app_key: str | None = None,
    ) -> None:
        """Initialize with Mathpix credentials.

        Resolution order (first wins):
        1. Explicit *app_id* / *app_key* args.
        2. ``resolve_credential`` (env, config.yaml, opencode.json).
        """
        self._app_id = app_id or resolve_credential("MATHPIX_APP_ID")
        self._app_key = app_key or resolve_credential("MATHPIX_APP_KEY")

    # -- Protocol requirements -------------------------------------------------

    @property
    def engine_name(self) -> str:
        return EngineName.MATHPIX

    # -- recognise (public entry point) ---------------------------------------

    def recognize(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float = 120.0,
        languages: list[str] | None = None,
    ) -> EngineOutput:
        """Send *image_path* to the Mathpix ``/v3/text`` endpoint.

        The API call itself is retried with exponential backoff via
        ``_post_to_mathpix()``.
        """
        t0 = time.perf_counter()

        # --- Read image bytes (not retried) ---
        try:
            raw_bytes = image_path.read_bytes()
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                error=f"Failed to read image file: {exc}",
                duration_sec=elapsed,
            )

        # --- Guard: requests available? ---
        try:
            import requests  # noqa: F401
        except ImportError:
            elapsed = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                error="requests library not installed. Install with: pip install requests",
                duration_sec=elapsed,
            )

        # --- Guard: credentials ---
        if not self._app_id or not self._app_key:
            elapsed = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                error="Mathpix credentials not configured",
                duration_sec=elapsed,
            )

        # --- API call (retry-wrapped) ---
        try:
            result_text = self._post_to_mathpix(raw_bytes, timeout_sec)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            retries = self._post_to_mathpix.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
            return EngineOutput(
                engine=self.engine_name,
                error=str(exc),
                duration_sec=elapsed,
                retries=retries,
            )

        elapsed = time.perf_counter() - t0
        retries = self._post_to_mathpix.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
        return EngineOutput(
            engine=self.engine_name,
            text=result_text,
            duration_sec=elapsed,
            retries=retries,
        )

    # -- internal (retry-wrapped) ---------------------------------------------

    @with_api_retry()
    def _post_to_mathpix(self, raw_bytes: bytes, timeout_sec: float) -> str:
        """POST the image bytes to Mathpix /v3/text — raises on failure."""
        import requests

        options = {
            "math_inline_delimiters": ["$", "$"],
            "rm_spaces": True,
        }
        response = requests.post(
            "https://api.mathpix.com/v3/text",
            files={"file": ("page.png", raw_bytes, "image/png")},
            data={"options_json": json.dumps(options)},
            headers={
                "app_id": self._app_id,
                "app_key": self._app_key,
            },
            timeout=timeout_sec,
        )
        response.raise_for_status()
        result: dict[str, object] = response.json()

        if "error" in result:
            raise RuntimeError(str(result["error"]))

        return str(result.get("text", ""))

    # -- health ---------------------------------------------------------------

    def health_check(self) -> bool:
        """Return ``True`` when credentials are present."""
        try:
            return bool(self._app_id and self._app_key)
        except Exception:
            return False
