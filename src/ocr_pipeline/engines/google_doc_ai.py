from __future__ import annotations

import time
from pathlib import Path

from .base import with_api_retry
from ..models import EngineName, EngineOutput


class GoogleDocAiEngine:
    """Google Document AI OCR engine (Enterprise Document OCR processor)."""

    def __init__(
        self,
        project_id: str,
        processor_id: str = "8081d1d423002a96",
        location: str = "us",
    ) -> None:
        self.project_id = project_id
        self.processor_id = processor_id
        self.location = location
        self._client = None

    @property
    def engine_name(self) -> str:
        return EngineName.GOOGLE_DOC_AI

    @property
    def _processor_name(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.location}/processors/{self.processor_id}"
        )

    def _get_client(self):
        """Lazy-init the Document AI client.

        Tries API key auth first (``GOOGLE_API_KEY`` env var), then falls
        back to Application Default Credentials (ADC / service account).
        """
        if self._client is None:
            import os

            from google.api_core.client_options import ClientOptions
            from google.cloud import documentai

            api_key = os.environ.get("GOOGLE_API_KEY", "")
            if api_key:
                opts = ClientOptions(
                    api_endpoint=f"{self.location}-documentai.googleapis.com",
                    api_key=api_key,
                )
            else:
                opts = ClientOptions(
                    api_endpoint=f"{self.location}-documentai.googleapis.com",
                )
            self._client = documentai.DocumentProcessorServiceClient(
                client_options=opts,
            )
        return self._client

    # -- recognise (public entry point) ---------------------------------------

    def recognize(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float = 120.0,
        languages: list[str] | None = None,
    ) -> EngineOutput:
        """Run Google Document AI OCR on a single PNG image.

        The ``process_document`` RPC is wrapped with exponential-backoff
        retry via ``_call_doc_ai()``.
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

        # --- Guard: SDK available? ---
        try:
            from google.cloud import documentai  # noqa: F401, F811
        except ImportError:
            elapsed = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                error=(
                    "Google Document AI SDK not installed. "
                    "Install with: pip install google-cloud-documentai"
                ),
                duration_sec=elapsed,
            )

        # --- RPC call (retry-wrapped) ---
        try:
            text = self._call_doc_ai(raw_bytes, timeout_sec)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            retries = self._call_doc_ai.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
            return EngineOutput(
                engine=self.engine_name,
                error=str(exc),
                duration_sec=elapsed,
                retries=retries,
            )

        elapsed = time.perf_counter() - t0
        retries = self._call_doc_ai.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
        return EngineOutput(
            engine=self.engine_name,
            text=text,
            duration_sec=elapsed,
            retries=retries,
        )

    # -- internal (retry-wrapped) ---------------------------------------------

    @with_api_retry()
    def _call_doc_ai(self, raw_bytes: bytes, timeout_sec: float) -> str:
        """Invoke ``process_document`` — raises on failure so tenacity retries."""
        from google.cloud import documentai  # noqa: F811

        client = self._get_client()
        raw_document = documentai.RawDocument(
            content=raw_bytes,
            mime_type="image/png",
        )
        request = documentai.ProcessRequest(
            name=self._processor_name,
            raw_document=raw_document,
        )
        result = client.process_document(request=request, timeout=timeout_sec)
        return result.document.text

    # -- health ---------------------------------------------------------------

    def health_check(self) -> bool:
        """Check that Google credentials and processor are available."""
        try:
            self._get_client()
            return True
        except Exception:
            return False
