"""Domain-specific exceptions for the OCR pipeline."""

from __future__ import annotations


class OcrPipelineError(Exception):
    """Base exception for all OCR pipeline errors."""


class ConfigError(OcrPipelineError):
    """Configuration errors (missing files, invalid values, env-var issues)."""


class EngineError(OcrPipelineError):
    """Wraps an OCR engine failure."""

    def __init__(self, message: str, engine_name: str) -> None:
        super().__init__(message)
        self.engine_name = engine_name


class CheckpointError(OcrPipelineError):
    """Checkpoint read/write/migration failures."""


class RenderError(OcrPipelineError):
    """PDF page rendering failures."""


class MergeError(OcrPipelineError):
    """VLM merge failures."""
