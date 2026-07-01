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
                "MarkerEngine requires a venv_path. "
                "Provide it via config.marker_venv or pass it explicitly."
            )
        return MarkerEngine(venv_path=venv_path)

    if name == EngineName.MATHPIX:
        return MathpixEngine()

    if name == EngineName.GOOGLE_DOC_AI:
        project_id = (
            getattr(config, "google_cloud_project", None) if config is not None else None
        ) or os.environ.get("GOOGLE_CLOUD_PROJECT", "")

        processor_id = (
            getattr(config, "google_processor_id", None) if config is not None else None
        )
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

    if name == EngineName.SURYA2:
        venv = None
        if config is not None:
            venv = getattr(config, "surya2_venv", None) or getattr(config, "marker_venv", None)
        return Surya2Engine(venv_path=Path(venv) if venv else None)

    # Should never reach here
    raise ValueError(f"Unknown engine: {name!r}")
