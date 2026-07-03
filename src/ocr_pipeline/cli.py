#!/usr/bin/env python3
"""CLI entry point for the OCR pipeline.

Usage:
    uv run ocr-pipeline --input ./pdfs/ --output ./out/
    uv run ocr-pipeline -i ./pdfs/ -o ./out/ --engines marker,mathpix
    uv run ocr-pipeline -i ./pdfs/ -o ./out/ --config config.yaml
    uv run ocr-pipeline -i ./pdfs/ -o ./out/ --dry-run
    uv run ocr-pipeline -i ./pdfs/ -o ./out/ --test
    uv run ocr-pipeline --list-profiles
    uv run ocr-pipeline -i ./pdfs/ -o ./out/ --profile academic
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from .config import ConfigLoader, PipelineConfig
from .languages import (
    LANGUAGE_NAMES,
    _engine_support_label,
    list_languages_for_engine,
    warn_unknown_languages,
)
from .pipeline import Pipeline
from .profiles import (
    get_profile,
)

# ---------------------------------------------------------------------------
# CLI-arg → PipelineConfig mapping
# ---------------------------------------------------------------------------

# Each entry: (cli_attr_name, config_field_name, optional_transform)
# Entries with default=None in argparse; applied only when not None.
_CLI_VALUE_MAP: list[tuple[str, str, Callable[[Any], Any] | None]] = [
    ("engines", "engines", lambda v: [e.strip() for e in v.split(",") if e.strip()]),
    ("vlm_model", "vlm_model", None),
    ("vlm_agreement", "vlm_agreement_threshold", None),
    ("budget", "budget_cap_usd", None),
    ("column_layout", "column_layout", None),
    ("langs", "languages", lambda v: [lang.strip() for lang in v.split(",") if lang.strip()]),
    ("dpi", "render_dpi", None),
    ("workers", "max_workers", None),
    ("marker_concurrency", "marker_concurrency", None),
    ("max_retries", "max_retries", None),
    ("retry_base_delay", "retry_base_delay_sec", None),
    ("retry_max_delay", "retry_max_delay_sec", None),
    ("timeout", "api_timeout_sec", None),
    ("marker_venv", "marker_venv", None),
]

logger = logging.getLogger("ocr_pipeline")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="ocr-pipeline",
        description="Multi-engine OCR with VLM merge for PDF documents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run ocr-pipeline --input ./pdfs/ --output ./out/\n"
            "  uv run ocr-pipeline -i ./pdfs/ -o ./out/ --engines marker,mathpix"
            " --vlm-model gemini-2.0-flash-001\n"
            "  uv run ocr-pipeline -i ./pdfs/ -o ./out/ --budget 10.0"
            " --profile academic --langs en,la\n"
            "  uv run ocr-pipeline -i ./pdfs/ -o ./out/ --dry-run\n"
            "  uv run ocr-pipeline -i ./pdfs/ -o ./out/ --test\n"
        ),
    )

    # -- Input / output ------------------------------------------------------
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=None,
        help="Input directory containing PDF files (required unless --config is used)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output directory for processed results (required unless --config is used)",
    )

    # -- Config file ---------------------------------------------------------
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help="Path to config.yaml (CLI args override YAML values)",
    )

    # -- Engine selection ----------------------------------------------------
    parser.add_argument(
        "--engines",
        "-e",
        default=None,
        help="Comma-separated engine names (default: marker)",
    )

    # -- VLM -----------------------------------------------------------------
    parser.add_argument(
        "--vlm-model",
        default=None,
        help="VLM model name (e.g. gemini-2.0-flash-001)",
    )
    parser.add_argument(
        "--no-vlm",
        action="store_true",
        help="Disable VLM merge",
    )
    parser.add_argument(
        "--vlm-agreement",
        type=float,
        default=None,
        help="Agreement threshold to skip VLM (default: 0.97)",
    )

    # -- Budget --------------------------------------------------------------
    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Budget cap in USD (e.g. 50.0)",
    )

    # -- Content hints -------------------------------------------------------
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Document profile name (auto-fills engines, model, and languages). One of: general, academic, mathematical, legal, technical, books.",
    )
    parser.add_argument(
        "--column-layout",
        default=None,
        help="Column layout: single, dual, auto",
    )
    parser.add_argument(
        "--langs",
        default=None,
        help="Comma-separated language codes (e.g. en,la,fr)",
    )

    # -- Rendering -----------------------------------------------------------
    parser.add_argument(
        "--dpi",
        type=int,
        default=None,
        help="Render DPI (default: 300)",
    )

    # -- Concurrency ---------------------------------------------------------
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Max worker threads (default: 4)",
    )
    parser.add_argument(
        "--marker-concurrency",
        type=int,
        default=None,
        help="Max concurrent Marker subprocesses (default: 1)",
    )

    # -- Retry ---------------------------------------------------------------
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Max API retries (default: 3)",
    )
    parser.add_argument(
        "--retry-base-delay",
        type=float,
        default=None,
        help="Base retry delay in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--retry-max-delay",
        type=float,
        default=None,
        help="Max retry delay in seconds (default: 60.0)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="API timeout in seconds (default: 120.0)",
    )

    # -- Modes ---------------------------------------------------------------
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="Test mode (first 3 pages only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without running OCR",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available document profiles and exit",
    )
    parser.add_argument(
        "--list-engines",
        action="store_true",
        help="List available OCR engines and exit",
    )
    parser.add_argument(
        "--list-languages",
        action="store_true",
        help="List supported language codes and exit",
    )
    parser.add_argument(
        "--list-languages-for",
        type=str,
        default=None,
        metavar="ENGINE",
        help="List languages supported by ENGINE (marker, surya2, google_doc_ai, tesseract)",
    )

    # -- Post-processing -----------------------------------------------------
    parser.add_argument(
        "--no-postprocess",
        action="store_true",
        help="Skip post-processing cleanup",
    )

    # -- Logging -------------------------------------------------------------
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging (DEBUG level)",
    )

    # -- Engine-specific paths -----------------------------------------------
    parser.add_argument(
        "--marker-venv",
        default=None,
        help="Path to Marker virtual environment",
    )

    return parser


# ---------------------------------------------------------------------------
# Config builder (priority: CLI > YAML > dataclass defaults)
# ---------------------------------------------------------------------------


def _build_config(args: argparse.Namespace) -> PipelineConfig:
    """Build a PipelineConfig from CLI args, optionally layered over a YAML baseline.

    Priority: CLI arguments > config.yaml > PipelineConfig dataclass defaults.
    """
    # Baseline: YAML config (which itself falls back to dataclass defaults)
    if args.config:
        config = ConfigLoader.from_yaml(args.config)
    elif args.input is not None and args.output is not None:
        config = PipelineConfig(input_dir=args.input, output_dir=args.output)
    else:
        config = PipelineConfig(input_dir=Path("."), output_dir=Path("."))

    # Override input/output from CLI only when explicitly provided
    if args.input is not None:
        config.input_dir = args.input
    if args.output is not None:
        config.output_dir = args.output

    # Profile auto-fill: use profile defaults for fields not explicitly set via CLI
    if args.profile is not None:
        profile = get_profile(args.profile)
        config.profile = args.profile
        if args.engines is None:
            config.engines = list(profile.suggested_engines)
        if args.vlm_model is None:
            config.vlm_model = profile.suggested_model
        if args.langs is None:
            config.languages = list(profile.suggested_languages)

    # Apply value overrides (only when user explicitly provided the flag)
    for cli_attr, cfg_field, transform in _CLI_VALUE_MAP:
        value = getattr(args, cli_attr)
        if value is not None:
            if transform is not None:
                value = transform(value)
            setattr(config, cfg_field, value)

    # Boolean flags (action="store_true", default=False)
    if args.no_vlm:
        config.vlm_enabled = False
    if args.no_postprocess:
        config.postprocess_enabled = False
    if args.test:
        config.test_mode = True

    return config


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def _dry_run(config: PipelineConfig) -> None:
    """Print what would be processed without running the pipeline."""
    pdf_paths = sorted(config.input_dir.rglob("*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found in {config.input_dir}")
        return

    print(f"Input directory:    {config.input_dir}")
    print(f"Output directory:   {config.output_dir}")
    print(f"PDFs found:         {len(pdf_paths)}")
    print(f"Engines:            {', '.join(config.engines)}")
    print(f"VLM merge:          {'enabled' if config.vlm_enabled else 'disabled'}")
    if config.vlm_enabled:
        print(f"VLM model:          {config.vlm_model}")
    print(f"Profile:             {config.profile}")
    print(f"Column layout:      {config.column_layout}")
    print(f"Languages:          {', '.join(config.languages)}")
    print(f"Render DPI:         {config.render_dpi}")
    print(f"Max workers:        {config.max_workers}")
    print(f"PDF concurrency:    {config.pdf_concurrency}")
    print(f"Marker concurrency: {config.marker_concurrency}")
    if config.budget_cap_usd is not None:
        print(f"Budget cap:         ${config.budget_cap_usd:.2f}")
    print(f"Post-process:       {'enabled' if config.postprocess_enabled else 'disabled'}")
    print(f"Test mode:          {'yes' if config.test_mode else 'no'}")

    print("\n--- PDFs that would be processed ---")
    for pdf_path in pdf_paths:
        rel = pdf_path.relative_to(config.input_dir)
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        print(f"  {rel}  ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# List-profiles
# ---------------------------------------------------------------------------


def _print_profiles() -> None:
    """Print all available document profiles and exit."""
    from .profiles import list_profiles as _list_profiles

    print("Available document profiles (use with --profile):\n")
    all_names = _list_profiles()
    for name in sorted(all_names):
        profile = get_profile(name)
        print(f"  {profile.name}")
        print(f"    Description: {profile.description}")
        engines = ", ".join(profile.suggested_engines)
        default_model = profile.suggested_model
        best = profile.best_model
        langs = ", ".join(profile.suggested_languages)
        print(f"    Suggested engines: {engines}")
        if best != default_model:
            print(f"    Default model: {default_model} (free tier)")
            print(f"    Best quality: {best} (paid -- add --vlm-model {best})")
        else:
            print(f"    Model: {default_model} (free tier)")
        print(f"    Suggested languages: {langs}")
        print("  Quick command:")
        print(f"    uv run ocr-pipeline --input ./pdfs/ --output ./out/ --profile {profile.name}")
        print()
    print(
        "The --profile flag auto-fills engines, model, and languages.\n"
        "VLM model defaults to gemini-2.5-flash (free tier available).\n"
        "You can override any value: --profile academic --engines mathpix --vlm-model claude-sonnet-5"
    )


# ---------------------------------------------------------------------------
# List-engines
# ---------------------------------------------------------------------------

_ENGINE_INFO: dict[str, dict[str, str]] = {
    "marker": {
        "header": "Local, free. General-purpose OCR (requires Marker venv).",
        "best_for": "general documents.",
        "install": "uv sync --extra marker",
        "cost": "free",
    },
    "mathpix": {
        "header": "API. Math-specialized OCR.",
        "best_for": "math-heavy PDFs, equations, LaTeX.",
        "requires": "MATHPIX_APP_ID and MATHPIX_APP_KEY",
        "free_tier": "1000 pages/month. Paid: ~$0.005/page",
    },
    "surya2": {
        "header": "Local, free. Next-gen VLM-based OCR (91 languages).",
        "best_for": "multilingual documents, layout analysis.",
        "install": "uv sync --extra surya2",
        "cost": "free",
    },
    "google_doc_ai": {
        "header": "API. Google Cloud Document AI (enterprise OCR).",
        "best_for": "forms, structured documents.",
        "requires": "GOOGLE_CLOUD_PROJECT and credentials",
        "free_tier": "500 pages/month. Paid: ~$0.0015/page",
    },
    "grobid": {
        "header": "API (local). Metadata extraction (not page OCR).",
        "best_for": "extracting title, authors, DOIs from academic PDFs.",
        "requires": "Docker running grobid container",
        "install": "docker run -d -p 8070:8070 lfoppiano/grobid:0.8.1",
        "cost": "free (runs locally)",
    },
    "tesseract": {
        "header": "Local, free. The most widely deployed OCR engine.",
        "best_for": "Arabic/RTL scripts, Cyrillic, and as a universal fallback.",
        "requires": "tesseract binary on PATH (brew install tesseract)",
        "install": "brew install tesseract (macOS) or apt install tesseract-ocr (Linux)",
        "cost": "free",
    },
}


def _print_engines() -> None:
    """Print all available OCR engines and exit."""
    print("Available OCR engines (use with --engines):\n")
    for name, info in _ENGINE_INFO.items():
        print(f"  {name}")
        for key, _label in [
            ("header", None),
            ("best_for", "Best for"),
            ("requires", "Requires"),
            ("install", "Install"),
            ("free_tier", "Free tier"),
            ("cost", "Cost"),
        ]:
            value = info.get(key)
            if value:
                if _label:
                    print(f"    {_label}: {value}")
                else:
                    print(f"    {value}")
        print()


# ---------------------------------------------------------------------------
# List-languages
# ---------------------------------------------------------------------------


def _print_languages() -> None:
    """Print all known language codes with names and engine support."""
    print("Supported languages (use with --langs):\n")
    for code in sorted(LANGUAGE_NAMES.keys()):
        name = LANGUAGE_NAMES[code]
        label = _engine_support_label(code)
        print(f"  {code:<6s} {name:<22s} {label}")


def _print_languages_for_engine(engine: str) -> None:
    """Print language codes supported by a specific engine."""
    try:
        codes = list_languages_for_engine(engine)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Languages supported by engine '{engine}':\n")
    for code in codes:
        name = LANGUAGE_NAMES.get(code, code)
        print(f"  {code:<6s} {name}")
    print(f"\n{len(codes)} language(s) total.")


# ---------------------------------------------------------------------------
# Stats printer
# ---------------------------------------------------------------------------


def _print_stats(stats: dict[str, Any]) -> None:
    """Print pipeline run statistics."""
    print("\n=== Pipeline Complete ===")
    print(f"PDFs processed:     {stats.get('pdfs_processed', 0)}")
    print(f"PDFs failed:        {stats.get('pdfs_failed', 0)}")
    print(f"Pages processed:    {stats.get('pages_processed', 0)}")
    print(f"Pages complete:     {stats.get('pages_complete', 0)}")
    print(f"Pages failed:       {stats.get('pages_failed', 0)}")
    print(f"Total cost:         ${stats.get('total_cost', 0.0):.2f}")
    print(f"Duration:           {stats.get('duration_sec', 0.0):.1f}s")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for the OCR pipeline."""
    parser = _build_parser()
    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Discovery commands (no input/output required)
    if args.list_profiles:
        _print_profiles()
        sys.exit(0)
    if args.list_engines:
        _print_engines()
        sys.exit(0)
    if args.list_languages:
        _print_languages()
        sys.exit(0)
    if args.list_languages_for:
        _print_languages_for_engine(args.list_languages_for)
        sys.exit(0)

    # Validate language codes early (before pipeline construction)
    if args.langs is not None:
        lang_list = [lang.strip() for lang in args.langs.split(",") if lang.strip()]
        warnings_list = warn_unknown_languages(lang_list)
        for warning in warnings_list:
            logger.warning(warning)

    # Build configuration
    config = _build_config(args)

    # Validate: input/output must be set via --config or --input/--output
    if args.config is None and args.input is None:
        parser.error(
            "No configuration provided. Either:\n"
            "  1. Use --config config.yaml (recommended), or\n"
            "  2. Use --input DIR --output DIR with optional CLI flags"
        )
    if not config.input_dir.exists():
        parser.error(
            f"Input directory does not exist: {config.input_dir}\n"
            "Provide --input, set input_dir in config.yaml, or set OCR_PIPELINE_INPUT_DIR."
        )

    # Ensure output directory exists
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # Dry run
    if args.dry_run:
        _dry_run(config)
        return

    # Full run
    logger.info(
        "Starting pipeline: %d engine(s) [%s], input=%s, output=%s",
        len(config.engines),
        ", ".join(config.engines),
        config.input_dir,
        config.output_dir,
    )

    try:
        pipeline = Pipeline(config)
        stats = pipeline.run()
        _print_stats(stats)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
