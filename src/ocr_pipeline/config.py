"""Pipeline configuration model and loader."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ocr_pipeline.errors import ConfigError


@dataclass
class PipelineConfig:
    """All configuration for an OCR pipeline run."""

    # -- Input / output ------------------------------------------------------
    input_dir: Path
    output_dir: Path
    checkpoint_dir: Path | None = None  # defaults to output_dir/.checkpoint/
    input_extensions: list[str] = field(default_factory=lambda: ["pdf"])
    """File extensions to glob for in ``input_dir`` (without leading dot).
    Default ``["pdf"]`` for backward compatibility.  Set to
    ``["pdf", "epub", "docx", "txt"]`` for multi-format ingestion."""

    # -- Engine selection ----------------------------------------------------
    engines: list[str] = field(default_factory=lambda: ["marker"])
    # Valid: "google_doc_ai", "mathpix", "marker", "surya2", "tesseract"

    # -- VLM merge -----------------------------------------------------------
    vlm_enabled: bool = True
    vlm_model: str = "gemini-2.5-flash"
    vlm_fallback_model: str = "claude-sonnet-5"
    vlm_system_prompt: str = ""  # empty = use built-in default
    vlm_agreement_threshold: float = 0.97  # skip VLM when engines agree >= this
    vlm_max_tokens: int = 8192
    vlm_cost_per_call: float = 0.00015  # Gemini 2.5 Flash per-page estimate (~$0.00013 actual)

    # -- Rendering -----------------------------------------------------------
    render_dpi: int = 300
    text_extraction_flags: int | None = (
        None  # None = use defaults (PRESERVE_WHITESPACE | PRESERVE_LIGATURES)
    )

    # -- Post-processing (self-healing) --------------------------------------
    postprocess_enabled: bool = True
    postprocess_steps: list[str] = field(
        default_factory=lambda: [
            "soft_hyphens",
            "em_dash_breaks",
            "whitespace_normalize",
            "ligature_expand",
            "stray_control_chars",
        ]
    )

    # -- Cost control --------------------------------------------------------
    budget_cap_usd: float | None = None
    engine_cost_per_page: dict[str, float] = field(
        default_factory=lambda: {
            "google_doc_ai": 0.0015,
            "mathpix": 0.005,
            "marker": 0.0,
            "surya2": 0.0,
            "tesseract": 0.0,
        }
    )

    # -- Concurrency ---------------------------------------------------------
    max_workers: int = 4
    marker_concurrency: int = 1
    surya2_concurrency: int = 1
    pdf_concurrency: int = 2

    # -- Retry (applies to ALL API calls) ------------------------------------
    max_retries: int = 3
    retry_base_delay_sec: float = 1.0
    retry_max_delay_sec: float = 60.0
    api_timeout_sec: float = 120.0

    # -- Document profile ----------------------------------------------------
    profile: str = "general"  # "general", "academic", "mathematical", "legal", "technical", "books"
    column_layout: str = "auto"  # "single", "dual", "auto"
    languages: list[str] = field(default_factory=lambda: ["en"])

    # -- Output formats -------------------------------------------------------
    output_formats: list[str] = field(default_factory=lambda: ["markdown"])
    # Valid: "markdown", "json", "alto"

    # -- Test mode ------------------------------------------------------------
    test_mode: bool = False  # limit to first 3 pages per PDF

    # -- Engine-specific paths / IDs -----------------------------------------
    marker_venv: str | None = None  # path to Marker's isolated venv, resolved at load time
    surya2_venv: str | None = None  # path to Surya 2's isolated venv (falls back to marker_venv)
    google_processor_id: str = ""  # Google Doc AI processor ID
    grobid_url: str = "http://localhost:8070"  # GROBID REST API URL
    vlm_metadata_model: str = "gemini-2.5-flash"  # VLM model for metadata extraction
    include_metadata_per_page: bool = True
    """Prepend a metadata comment to each page file so standalone pages
    identify their document (title, author, language, page number)."""

    def _resolve_marker_venv(self, config_dir: Path | None = None) -> None:
        """Resolve a relative ``marker_venv`` against *config_dir*.

        If *config_dir* is provided and ``marker_venv`` is relative,
        resolve it against *config_dir*.  Otherwise, set to ``None``
        (disabled) — we never guess a location.
        """
        if not self.marker_venv:  # None or empty string
            self.marker_venv = None
            return
        marker_path = Path(self.marker_venv)
        if marker_path.is_absolute():
            self.marker_venv = str(marker_path)
            return
        if config_dir is not None:
            self.marker_venv = str((config_dir / marker_path).resolve())
        else:
            self.marker_venv = None

    # -- Credentials (set via env / YAML, never committed) -------------------
    mathpix_app_id: str = ""
    mathpix_app_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    google_application_credentials: str = ""  # path to service-account JSON
    google_cloud_project: str = ""


class ConfigLoader:
    """Load PipelineConfig from YAML files or environment variables."""

    # Environment variable mapping: (config_field, env_var, parser)
    _ENV_MAP: list[tuple[str, str, type | None]] = [
        ("input_dir", "OCR_PIPELINE_INPUT_DIR", Path),
        ("output_dir", "OCR_PIPELINE_OUTPUT_DIR", Path),
        ("checkpoint_dir", "OCR_PIPELINE_CHECKPOINT_DIR", Path),
        ("input_extensions", "OCR_PIPELINE_INPUT_EXTENSIONS", None),  # comma-separated -> list
        ("engines", "OCR_PIPELINE_ENGINES", None),  # comma-separated -> list
        ("vlm_enabled", "OCR_PIPELINE_VLM_ENABLED", None),  # "true"/"false"
        ("vlm_model", "OCR_PIPELINE_VLM_MODEL", str),
        ("vlm_fallback_model", "OCR_PIPELINE_VLM_FALLBACK_MODEL", str),
        ("vlm_system_prompt", "OCR_PIPELINE_VLM_SYSTEM_PROMPT", str),
        ("vlm_agreement_threshold", "OCR_PIPELINE_VLM_AGREEMENT_THRESHOLD", float),
        ("vlm_max_tokens", "OCR_PIPELINE_VLM_MAX_TOKENS", int),
        ("vlm_cost_per_call", "OCR_PIPELINE_VLM_COST_PER_CALL", float),
        ("render_dpi", "OCR_PIPELINE_RENDER_DPI", int),
        ("text_extraction_flags", "OCR_PIPELINE_TEXT_EXTRACTION_FLAGS", int),
        ("postprocess_enabled", "OCR_PIPELINE_POSTPROCESS_ENABLED", None),
        ("budget_cap_usd", "OCR_PIPELINE_BUDGET_CAP_USD", float),
        ("max_workers", "OCR_PIPELINE_MAX_WORKERS", int),
        ("marker_concurrency", "OCR_PIPELINE_MARKER_CONCURRENCY", int),
        ("surya2_concurrency", "OCR_PIPELINE_SURYA2_CONCURRENCY", int),
        ("pdf_concurrency", "OCR_PIPELINE_PDF_CONCURRENCY", int),
        ("max_retries", "OCR_PIPELINE_MAX_RETRIES", int),
        ("retry_base_delay_sec", "OCR_PIPELINE_RETRY_BASE_DELAY_SEC", float),
        ("retry_max_delay_sec", "OCR_PIPELINE_RETRY_MAX_DELAY_SEC", float),
        ("api_timeout_sec", "OCR_PIPELINE_API_TIMEOUT_SEC", float),
        ("profile", "OCR_PIPELINE_PROFILE", str),
        ("column_layout", "OCR_PIPELINE_COLUMN_LAYOUT", str),
        ("output_formats", "OCR_PIPELINE_OUTPUT_FORMATS", None),  # comma-separated -> list
        ("marker_venv", "OCR_PIPELINE_MARKER_VENV", str),
        ("surya2_venv", "OCR_PIPELINE_SURYA2_VENV", str),
        ("google_processor_id", "OCR_PIPELINE_GOOGLE_PROCESSOR_ID", str),
        ("grobid_url", "GROBID_URL", str),
        ("vlm_metadata_model", "OCR_PIPELINE_VLM_METADATA_MODEL", str),
        (
            "include_metadata_per_page",
            "OCR_PIPELINE_INCLUDE_METADATA_PER_PAGE",
            None,
        ),  # bool handled via value.lower() inline
        ("mathpix_app_id", "MATHPIX_APP_ID", str),
        ("mathpix_app_key", "MATHPIX_APP_KEY", str),
        ("anthropic_api_key", "ANTHROPIC_API_KEY", str),
        ("gemini_api_key", "GEMINI_API_KEY", str),
        ("google_application_credentials", "GOOGLE_APPLICATION_CREDENTIALS", str),
        ("google_cloud_project", "GOOGLE_CLOUD_PROJECT", str),
    ]

    @classmethod
    def from_yaml(cls, path: Path) -> PipelineConfig:
        """Load configuration from a YAML file.

        Raises:
            ConfigError: if the file is missing or contains invalid values.
        """
        path = Path(path)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")

        try:
            import yaml
        except ImportError:
            raise ConfigError(
                "PyYAML is required for YAML config loading. Install it with: uv add pyyaml"
            )

        with open(path, "r") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        cfg = cls._from_dict(raw)
        cfg._resolve_marker_venv(path.parent)
        return cfg

    @classmethod
    def from_env(cls) -> PipelineConfig:
        """Load configuration from environment variables.

        Requires at least ``OCR_PIPELINE_INPUT_DIR`` and ``OCR_PIPELINE_OUTPUT_DIR``
        to be set.  All other fields use their dataclass defaults.

        Raises:
            ConfigError: if required environment variables are missing.
        """
        overrides: dict[str, Any] = {}

        for field_name, env_var, parser in cls._ENV_MAP:
            value = os.environ.get(env_var)
            if value is None:
                continue

            if parser is None:
                # Special handlers
                if field_name == "engines":
                    overrides[field_name] = [e.strip() for e in value.split(",") if e.strip()]
                elif field_name in ("vlm_enabled", "postprocess_enabled"):
                    overrides[field_name] = value.lower() in ("1", "true", "yes")
                elif field_name == "postprocess_steps":
                    overrides[field_name] = [s.strip() for s in value.split(",") if s.strip()]
                elif field_name == "output_formats":
                    overrides[field_name] = [s.strip() for s in value.split(",") if s.strip()]
                elif field_name == "input_extensions":
                    overrides[field_name] = [s.strip() for s in value.split(",") if s.strip()]
                else:
                    overrides[field_name] = value
            elif parser is Path:
                overrides[field_name] = Path(value)
            else:
                overrides[field_name] = parser(value)  # type: ignore[call-arg]

        if "input_dir" not in overrides:
            raise ConfigError("OCR_PIPELINE_INPUT_DIR environment variable is required")
        if "output_dir" not in overrides:
            raise ConfigError("OCR_PIPELINE_OUTPUT_DIR environment variable is required")

        # Build a config from defaults, then patch in overrides.
        # We need at minimum input_dir and output_dir to construct the object.
        cfg = PipelineConfig(
            input_dir=overrides.pop("input_dir"),
            output_dir=overrides.pop("output_dir"),
        )

        for key, val in overrides.items():
            if hasattr(cfg, key):
                setattr(cfg, key, val)

        cfg._resolve_marker_venv(None)  # relative paths become None (disabled)
        return cfg

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten_dict(raw: dict[str, Any]) -> dict[str, Any]:
        """Unpack nested YAML sections into flat keys.

        YAML like ``vlm: {enabled: true}`` becomes ``vlm_enabled: true``.
        Sections that are already flat (``engines``, ``languages``,
        ``column_layout``, ``engine_cost_per_page``) are left untouched.
        """
        result = dict(raw)
        for section in ("vlm", "postprocess", "retry"):
            if section in result and isinstance(result[section], dict):
                for k, v in result[section].items():
                    result[f"{section}_{k}"] = v
        return result

    @classmethod
    def _from_dict(cls, raw: dict[str, Any]) -> PipelineConfig:
        """Build a PipelineConfig from a raw dict (from YAML)."""
        raw = cls._flatten_dict(raw)
        _coerce_path = cls._coerce_path
        _coerce_str_list = cls._coerce_str_list

        return PipelineConfig(
            # Input / output
            input_dir=_coerce_path(raw, "input_dir"),
            output_dir=_coerce_path(raw, "output_dir"),
            checkpoint_dir=cls._coerce_optional_path(raw, "checkpoint_dir"),
            input_extensions=_coerce_str_list(raw.get("input_extensions", ["pdf"])),
            # Engine selection
            engines=_coerce_str_list(raw.get("engines", ["marker"])),
            # VLM
            vlm_enabled=bool(raw.get("vlm_enabled", True)),
            vlm_model=str(raw.get("vlm_model", "gemini-2.5-flash")),
            vlm_fallback_model=str(raw.get("vlm_fallback_model", "claude-sonnet-5")),
            vlm_system_prompt=str(raw.get("vlm_system_prompt", "")),
            vlm_agreement_threshold=float(raw.get("vlm_agreement_threshold", 0.97)),
            vlm_max_tokens=int(raw.get("vlm_max_tokens", 8192)),
            vlm_cost_per_call=float(raw.get("vlm_cost_per_call", 0.00015)),
            # Rendering
            render_dpi=int(raw.get("render_dpi", 300)),
            text_extraction_flags=raw.get("text_extraction_flags"),  # None = use PyMuPDF defaults
            # Post-processing
            postprocess_enabled=bool(raw.get("postprocess_enabled", True)),
            postprocess_steps=_coerce_str_list(
                raw.get(
                    "postprocess_steps",
                    [
                        "soft_hyphens",
                        "em_dash_breaks",
                        "whitespace_normalize",
                        "ligature_expand",
                        "stray_control_chars",
                    ],
                )
            ),
            # Cost control
            budget_cap_usd=raw.get("budget_cap_usd"),  # None or float
            engine_cost_per_page=raw.get(
                "engine_cost_per_page",
                {
                    "google_doc_ai": 0.0015,
                    "mathpix": 0.005,
                    "marker": 0.0,
                    "surya2": 0.0,
                    "olmocr": 0.0,
                    "tesseract": 0.0,
                },
            ),
            # Concurrency
            max_workers=int(raw.get("max_workers", 4)),
            marker_concurrency=int(raw.get("marker_concurrency", 1)),
            surya2_concurrency=int(raw.get("surya2_concurrency", 1)),
            pdf_concurrency=int(raw.get("pdf_concurrency", 2)),
            # Retry
            max_retries=int(raw.get("max_retries", 3)),
            retry_base_delay_sec=float(raw.get("retry_base_delay_sec", 1.0)),
            retry_max_delay_sec=float(raw.get("retry_max_delay_sec", 60.0)),
            api_timeout_sec=float(raw.get("api_timeout_sec", 120.0)),
            # Content hints
            profile=str(raw.get("profile", "general")),
            column_layout=str(raw.get("column_layout", "auto")),
            languages=_coerce_str_list(raw.get("languages", ["en"])),
            # Output formats
            output_formats=_coerce_str_list(raw.get("output_formats", ["markdown"])),
            # Engine-specific
            marker_venv=raw.get("marker_venv"),  # None if not configured
            surya2_venv=raw.get("surya2_venv"),  # None if not configured
            google_processor_id=str(raw.get("google_processor_id", "")),
            grobid_url=str(raw.get("grobid_url", "http://localhost:8070")),
            vlm_metadata_model=str(raw.get("vlm_metadata_model", "gemini-2.5-flash")),
            include_metadata_per_page=bool(raw.get("include_metadata_per_page", True)),
            # Credentials
            mathpix_app_id=str(raw.get("mathpix_app_id", "")),
            mathpix_app_key=str(raw.get("mathpix_app_key", "")),
            anthropic_api_key=str(raw.get("anthropic_api_key", "")),
            gemini_api_key=str(raw.get("gemini_api_key", "")),
            google_application_credentials=str(raw.get("google_application_credentials", "")),
            google_cloud_project=str(raw.get("google_cloud_project", "")),
        )

    @staticmethod
    def _coerce_path(
        raw: dict[str, Any],
        key: str,
        *,
        required: bool = True,
    ) -> Path:
        """Coerce a config value to a Path.  Raises ConfigError if missing
        and *required* is True."""
        value = raw.get(key)
        if value is None:
            if required:
                raise ConfigError(f"Missing required config key: {key!r}")
            raise TypeError(
                f"_coerce_path({key!r}, required=False) returned None"
            )  # pragma: no cover
        return Path(value)

    @staticmethod
    def _coerce_optional_path(
        raw: dict[str, Any],
        key: str,
    ) -> Path | None:
        value = raw.get(key)
        if value is None or value == "":
            return None
        return Path(value)

    # ------------------------------------------------------------------
    # Credential injection (for MCP-server fallback paths)
    # ------------------------------------------------------------------

    @staticmethod
    def apply_env_credentials(cfg: PipelineConfig) -> None:
        """Read credential / connection env vars and apply them to *cfg*.

        Designed for the MCP-server fallback path, where
        ``from_env()`` fails (required dirs not set) but we still
        want to pick up API keys from the environment.

        Only sets fields when the corresponding env var is present
        and non-empty.
        """
        _CREDENTIAL_ENV_MAP: list[tuple[str, str]] = [
            ("mathpix_app_id", "MATHPIX_APP_ID"),
            ("mathpix_app_key", "MATHPIX_APP_KEY"),
            ("anthropic_api_key", "ANTHROPIC_API_KEY"),
            ("gemini_api_key", "GEMINI_API_KEY"),
            ("google_cloud_project", "GOOGLE_CLOUD_PROJECT"),
            ("google_application_credentials", "GOOGLE_APPLICATION_CREDENTIALS"),
            ("grobid_url", "GROBID_URL"),
        ]
        for field_name, env_var in _CREDENTIAL_ENV_MAP:
            value = os.environ.get(env_var, "")
            if value:
                setattr(cfg, field_name, value)

    @staticmethod
    def _coerce_str_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            return [s.strip() for s in value.split(",") if s.strip()]
        return [str(value)]
