"""OCR engines package.

Exports all engine classes, the base types, retry infrastructure,
circuit breaker, and a ``create_engine`` factory.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..models import EngineName, EngineOutput

from .base import (
    CircuitBreaker,
    CredentialStore,
    OcrEngine,
    with_api_retry,
)
from .google_doc_ai import GoogleDocAiEngine
from .grobid import GrobidEngine
from .marker import MarkerEngine
from .mathpix import MathpixEngine
from .surya2 import Surya2Engine
from .tesseract import TesseractEngine
from .trocr import TrocrEngine

__all__ = [
    # Base types & infrastructure
    "CircuitBreaker",
    "CredentialStore",
    "EngineName",
    "EngineOutput",
    "OcrEngine",
    "with_api_retry",
    # Engine implementations
    "GoogleDocAiEngine",
    "GrobidEngine",
    "MarkerEngine",
    "MathpixEngine",
    "Surya2Engine",
    "TesseractEngine",
    "TrocrEngine",
    # Factory
    "create_engine",
]

# -- Engine registry ----------------------------------------------------------

_ENGINE_CLASSES: dict[str, type] = {
    EngineName.GOOGLE_DOC_AI: GoogleDocAiEngine,
    EngineName.MATHPIX: MathpixEngine,
    EngineName.MARKER: MarkerEngine,
    EngineName.GROBID: GrobidEngine,
    EngineName.SURYA2: Surya2Engine,
    EngineName.TESSERACT: TesseractEngine,
    EngineName.TROCR: TrocrEngine,
}


def create_engine(name: str, config: object | None = None) -> OcrEngine:
    """Instantiate the right engine class for *name*.

    *config* is an optional object with attributes that mirror
    ``PipelineConfig`` fields (e.g. ``marker_venv``, ``google_cloud_project``,
    ``google_processor_id``, ``google_location``).  When *config* is
    ``None``, engines that require constructor parameters fall back to
    environment variables.

    Raises:
        ValueError: If *name* is not a known engine identifier.
    """
    if name not in _ENGINE_CLASSES:
        raise ValueError(
            f"Unknown engine: {name!r}.  Valid engines: {', '.join(sorted(_ENGINE_CLASSES))}"
        )

    if name == EngineName.MARKER:
        venv_path = getattr(config, "marker_venv", None) if config is not None else None
        if venv_path is None:
            raise ValueError(
                "MarkerEngine requires a venv_path.\n"
                "Set marker_venv in config.yaml, or install with: uv sync --extra marker"
            )
        return MarkerEngine(venv_path=venv_path)

    if name == EngineName.MATHPIX:
        app_id = getattr(config, "mathpix_app_id", "") if config is not None else ""
        app_key = getattr(config, "mathpix_app_key", "") if config is not None else ""
        if not app_id:
            app_id = os.environ.get("MATHPIX_APP_ID", "")
        if not app_key:
            app_key = os.environ.get("MATHPIX_APP_KEY", "")
        if not app_id or not app_key:
            raise ValueError(
                "MathpixEngine requires credentials.\n"
                "Set mathpix_app_id and mathpix_app_key in config.yaml, "
                "or set MATHPIX_APP_ID and MATHPIX_APP_KEY env vars.\n"
                "Get keys at: https://mathpix.com"
            )
        return MathpixEngine()

    if name == EngineName.GOOGLE_DOC_AI:
        project_id = (
            getattr(config, "google_cloud_project", None) if config is not None else None
        ) or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        if not project_id:
            raise ValueError(
                "GoogleDocAiEngine requires a Google Cloud project.\n"
                "Set google_cloud_project in config.yaml or GOOGLE_CLOUD_PROJECT env var "
                "(and GOOGLE_API_KEY if not using a service account).\n"
                "See: https://cloud.google.com/document-ai"
            )

        processor_id = getattr(config, "google_processor_id", None) if config is not None else None
        if not processor_id:
            # Fall back to the engine class default (Google-provided OCR processor)
            import inspect

            sig = inspect.signature(GoogleDocAiEngine.__init__)
            processor_id = sig.parameters["processor_id"].default

        location = getattr(config, "google_location", "us") if config is not None else "us"
        return GoogleDocAiEngine(
            project_id=project_id,
            processor_id=processor_id,
            location=location,
        )

    if name == EngineName.GROBID:
        grobid_url = (
            getattr(config, "grobid_url", "http://localhost:8070")
            if config is not None
            else "http://localhost:8070"
        )
        return GrobidEngine(grobid_url=grobid_url)

    if name == EngineName.TESSERACT:
        tesseract_cmd = (
            getattr(config, "tesseract_cmd", "tesseract") if config is not None else "tesseract"
        )
        timeout = getattr(config, "api_timeout_sec", 120.0) if config is not None else 120.0
        return TesseractEngine(tesseract_cmd=tesseract_cmd, timeout_sec=timeout)

    if name == EngineName.SURYA2:
        venv = None
        if config is not None:
            venv = getattr(config, "surya2_venv", None) or getattr(config, "marker_venv", None)
        try:
            return Surya2Engine(venv_path=Path(venv) if venv else None)
        except ValueError:
            raise ValueError(
                "Surya2Engine requires a venv_path.\n"
                "Set surya2_venv in config.yaml, or install with: uv sync --extra surya2"
            )

    if name == EngineName.TROCR:
        return TrocrEngine()

    # Should never reach here
    raise ValueError(f"Unknown engine: {name!r}")
