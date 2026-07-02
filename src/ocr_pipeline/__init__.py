"""OCR Pipeline — multi-engine OCR with VLM merge for PDF documents."""

from .config import PipelineConfig, ConfigLoader
from .merger import VlmMerger, DefaultVlmMerger, StubVlmMerger
from .pipeline import Pipeline
from .profiles import DocumentProfile, PROFILES, get_profile, list_profiles

__all__ = [
    "Pipeline",
    "PipelineConfig",
    "ConfigLoader",
    "VlmMerger",
    "DefaultVlmMerger",
    "StubVlmMerger",
    "DocumentProfile",
    "PROFILES",
    "get_profile",
    "list_profiles",
]
