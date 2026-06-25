"""OCR Pipeline — multi-engine OCR with VLM merge for PDF documents."""

from .config import PipelineConfig, ConfigLoader
from .merger import VlmMerger, DefaultVlmMerger, StubVlmMerger
from .pipeline import Pipeline

__all__ = [
    "Pipeline",
    "PipelineConfig",
    "ConfigLoader",
    "VlmMerger",
    "DefaultVlmMerger",
    "StubVlmMerger",
]
