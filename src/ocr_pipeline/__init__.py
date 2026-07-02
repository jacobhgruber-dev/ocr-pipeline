"""OCR Pipeline — multi-engine OCR with VLM merge for PDF documents."""

from .config import PipelineConfig, ConfigLoader
from .languages import (
    LANGUAGE_NAMES,
    get_language_name,
    list_languages,
    list_languages_for_engine,
    validate_languages,
    warn_unknown_languages,
)
from .merger import VlmMerger, DefaultVlmMerger, StubVlmMerger
from .pipeline import Pipeline
from .profiles import (
    DocumentProfile,
    PROFILES,
    best_model,
    get_profile,
    list_profiles,
    suggested_engines,
    suggested_languages,
    suggested_model,
)

__all__ = [
    "Pipeline",
    "PipelineConfig",
    "ConfigLoader",
    "LANGUAGE_NAMES",
    "get_language_name",
    "list_languages",
    "list_languages_for_engine",
    "validate_languages",
    "warn_unknown_languages",
    "VlmMerger",
    "DefaultVlmMerger",
    "StubVlmMerger",
    "DocumentProfile",
    "PROFILES",
    "get_profile",
    "list_profiles",
    "suggested_engines",
    "suggested_languages",
    "suggested_model",
    "best_model",
]
