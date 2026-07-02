"""MCP server wrapper for OCR Pipeline — exposes OCR tools to opencode agents."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import ConfigLoader, PipelineConfig
from .engines import create_engine
from .languages import (
    LANGUAGE_NAMES,
    ENGINE_NAMES,
    list_languages_for_engine,
)
from .pipeline import Pipeline
from .profiles import (
    PROFILES,
    get_profile,
    list_profiles,
    suggested_engines,
    suggested_languages,
    suggested_model,
)

logger = logging.getLogger("ocr-pipeline-mcp")

mcp = FastMCP(
    "ocr-pipeline",
    instructions=(
        "OCR Pipeline MCP — OCR PDFs and single page images with multi-engine support.\n\n"
        "Tools:\n"
        "- ocr_pdf: Process a full PDF through the OCR pipeline (render→OCR→VLM merge).\n"
        "- ocr_page: OCR a single page image with a specific engine.\n"
        "- ocr_status: Check which OCR engines are available and healthy."
    ),
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_config(
    pdf_path: str,
    output_dir: str,
    engines: str,
    vlm_model: str,
    vlm_enabled: bool,
    content_type: str,
    languages: str,
    test_mode: bool,
    profile_name: str = "",
) -> PipelineConfig:
    """Build a PipelineConfig from tool parameters.

    Tries to load env-based config first (for marker_venv, credentials, etc.),
    then overrides with tool-supplied values.
    """
    pdf = Path(pdf_path).resolve()
    if not pdf.is_file():
        raise ValueError(f"PDF not found: {pdf_path}")

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    # Try env-based config first, then project config.yaml, then bare fallback.
    try:
        cfg = ConfigLoader.from_env()
    except Exception:
        try:
            cfg = ConfigLoader.from_yaml(Path("config.yaml"))
        except Exception:
            cfg = PipelineConfig(input_dir=pdf.parent, output_dir=out)
        ConfigLoader.apply_env_credentials(cfg)

    # Profile auto-fill: use profile suggestions for fields at their defaults.
    _default_engines = "marker"
    _default_vlm_model = "gemini-2.5-flash"
    _default_content_type = "general"
    _default_languages = "en"

    if profile_name:
        profile = get_profile(profile_name)
        if engines == _default_engines:
            engines = ",".join(suggested_engines(profile_name))
        if vlm_model == _default_vlm_model:
            vlm_model = suggested_model(profile_name)
        if content_type == _default_content_type:
            content_type = profile.content_type
        if languages == _default_languages:
            languages = ",".join(suggested_languages(profile_name))

    engine_list = [e.strip() for e in engines.split(",") if e.strip()]
    lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]

    # Override with tool-supplied values
    cfg.input_dir = pdf.parent
    cfg.output_dir = out
    cfg.engines = engine_list
    cfg.vlm_model = vlm_model
    cfg.vlm_enabled = vlm_enabled
    cfg.content_type = content_type
    cfg.languages = lang_list
    cfg.test_mode = test_mode

    return cfg


def _find_output_preview(output_dir: Path, max_chars: int = 2000) -> str:
    """Find the first completed page markdown in the output directory tree."""
    try:
        for item in sorted(output_dir.iterdir()):
            if not item.is_dir():
                continue
            preview_file = item / "page_0001_final.md"
            if preview_file.is_file():
                text = preview_file.read_text()
                if len(text) > max_chars:
                    text = text[:max_chars] + "\n..."
                return text
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def ocr_pdf(
    pdf_path: str,
    output_dir: str | None = None,
    engines: str = "marker",
    vlm_model: str = "gemini-2.5-flash",
    vlm_enabled: bool = True,
    content_type: str = "general",
    languages: str = "en",
    test_mode: bool = False,
    profile_name: str = "",
) -> dict[str, Any]:
    """OCR a PDF file through the full pipeline and return extracted markdown.

    Processes the PDF through render → multi-engine OCR → VLM merge,
    producing per-page markdown files in the output directory.

    Args:
        pdf_path: Absolute path to the PDF file.
        output_dir: Directory for output files (default: ./ocr_output/).
        engines: Comma-separated engine names (marker, mathpix, surya2, google_doc_ai).
        vlm_model: VLM model for merge (gemini-2.5-flash, claude-sonnet-4-6, etc.).
        vlm_enabled: Whether to use VLM to merge engine outputs.
        content_type: Document type hint (general, theological, academic, mathematical).
        languages: Comma-separated language codes (en, de, fr, la, grc, he, etc.).
        test_mode: If True, process only the first 3 pages.
        profile_name: Document profile name (auto-fills content_type, engines, model, languages).
    """
    output_dir = output_dir or "./ocr_output"

    try:
        cfg = _build_config(
            pdf_path,
            output_dir,
            engines,
            vlm_model,
            vlm_enabled,
            content_type,
            languages,
            test_mode,
            profile_name=profile_name,
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": f"Config error: {exc}"}

    try:
        pipeline = Pipeline(cfg)
        if not pipeline.engines:
            return {
                "status": "error",
                "message": (
                    f"No OCR engines available from [{engines}]. "
                    "Check that required credentials and paths are configured."
                ),
            }

        # process_one is synchronous (uses ThreadPoolExecutor internally).
        # Wrap in to_thread so the MCP handler doesn't block the event loop.
        stats = await asyncio.to_thread(pipeline.process_one, Path(pdf_path).resolve())

        text_preview = _find_output_preview(cfg.output_dir)

        return {
            "status": "ok",
            "pages_processed": stats.get("pages_processed", 0),
            "pages_complete": stats.get("pages_complete", 0),
            "pages_failed": stats.get("pages_failed", 0),
            "output_dir": str(cfg.output_dir),
            "text_preview": text_preview,
        }
    except Exception as exc:
        logger.exception("ocr_pdf failed for %s", pdf_path)
        return {"status": "error", "message": str(exc)}


@mcp.tool()
async def ocr_page(
    image_path: str,
    engine: str = "marker",
    languages: str = "en",
) -> dict[str, Any]:
    """OCR a single page image using a specific engine.

    Args:
        image_path: Absolute path to a PNG or JPEG image of a document page.
        engine: OCR engine to use (marker, mathpix, surya2, google_doc_ai).
        languages: Comma-separated language codes (e.g., "en,de,fr").
    """
    img = Path(image_path).resolve()
    if not img.is_file():
        return {"status": "error", "message": f"Image not found: {image_path}"}

    lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]

    # Load config for engine parameters (marker_venv, credentials, etc.)
    try:
        cfg = ConfigLoader.from_env()
    except Exception:
        try:
            cfg = ConfigLoader.from_yaml(Path("config.yaml"))
        except Exception:
            cfg = PipelineConfig(input_dir=img.parent, output_dir=Path("./ocr_output"))
        ConfigLoader.apply_env_credentials(cfg)

    try:
        engine_instance = create_engine(engine, cfg)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    if not engine_instance.health_check():
        return {
            "status": "error",
            "message": f"Engine '{engine}' health check failed — may need credentials or venv path",
        }

    try:
        t0 = time.perf_counter()
        result = await asyncio.to_thread(
            engine_instance.recognize,
            img,
            0,
            cfg.api_timeout_sec,
            lang_list,
        )
        duration = round(time.perf_counter() - t0, 2)

        if result.error:
            return {
                "status": "error",
                "engine": engine,
                "message": result.error,
                "duration_sec": duration,
            }

        return {
            "text": result.text,
            "engine": engine,
            "duration_sec": duration,
        }
    except Exception as exc:
        logger.exception("ocr_page failed for %s with engine %s", image_path, engine)
        return {"status": "error", "engine": engine, "message": str(exc)}


@mcp.tool()
async def ocr_profiles() -> dict[str, Any]:
    """List available document profiles for OCR processing.

    Returns all pre-registered document profiles with their names,
    content types, descriptions, suggested engines, and recommended
    VLM models. Use these with the content_type parameter of
    ocr_pdf to get tailored VLM system prompts.
    """
    result = []
    for profile in PROFILES.values():
        result.append(
            {
                "name": profile.name,
                "content_type": profile.content_type,
                "description": profile.description,
                "suggested_engines": suggested_engines(profile.name),
                "suggested_model": suggested_model(profile.name),
            }
        )
    return {"profiles": result}


@mcp.tool()
async def ocr_status() -> dict[str, Any]:
    """Check which OCR engines are available and their health status."""
    engine_names = ["marker", "mathpix", "surya2", "google_doc_ai", "grobid"]
    statuses: dict[str, bool | str] = {}

    # Load config to pick up any env-configured engine settings
    try:
        cfg = ConfigLoader.from_env()
    except Exception:
        try:
            cfg = ConfigLoader.from_yaml(Path("config.yaml"))
        except Exception:
            cfg = PipelineConfig(input_dir=Path("."), output_dir=Path("./ocr_output"))
        ConfigLoader.apply_env_credentials(cfg)

    for name in engine_names:
        try:
            engine_inst = create_engine(name, cfg)
            ok = engine_inst.health_check()
            statuses[name] = ok
        except Exception as exc:
            statuses[name] = f"unavailable: {exc}"

    return {
        "engines": statuses,
        "profiles_available": list_profiles(),
        "vlm_models_available": [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "claude-haiku-4-5",
            "claude-sonnet-4-6",
            "claude-3.5-haiku",
            "claude-3.5-sonnet",
        ],
    }


@mcp.tool()
async def ocr_languages(engine: str | None = None) -> dict[str, Any]:
    """List supported language codes and their names.

    Args:
        engine: If provided, filter to languages supported by this engine
                (marker, surya2, google_doc_ai). If omitted, list all.
    """
    if engine is not None:
        if engine not in ENGINE_NAMES:
            return {
                "status": "error",
                "message": (
                    f"Unknown engine: {engine!r}. "
                    f"Valid choices: {', '.join(sorted(ENGINE_NAMES.keys()))}"
                ),
            }
        try:
            codes = list_languages_for_engine(engine)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        langs = [{"code": code, "name": LANGUAGE_NAMES.get(code, code)} for code in codes]
        return {"languages": langs, "engine": engine, "count": len(langs)}

    # List all known languages
    langs = [{"code": code, "name": name} for code, name in LANGUAGE_NAMES.items()]
    langs.sort(key=lambda x: x["code"])
    return {"languages": langs, "count": len(langs)}


@mcp.tool()
async def ocr_metadata(pdf_path: str) -> dict[str, Any]:
    """Extract structured metadata from a PDF using GROBID.

    Runs GROBID independently of the OCR pipeline — useful for standalone
    metadata extraction or pre-processing before OCR.

    Requires a running GROBID server (default: ``http://localhost:8070``).
    Start with: ``docker run -p 8070:8070 lfoppiano/grobid:0.8.1``

    Args:
        pdf_path: Absolute path to the PDF file.

    Returns:
        Dict with ``status`` ("ok" or "error"), ``title``, ``authors``,
        ``doi``, ``journal``, ``volume``, ``issue``, ``year``, ``keywords``,
        ``abstract``, and ``pages``.
    """
    from .engines.grobid import GrobidEngine

    pdf = Path(pdf_path).resolve()
    if not pdf.is_file():
        return {"status": "error", "message": f"PDF not found: {pdf_path}"}

    # Load grobid_url from config or fall back to default
    try:
        cfg = ConfigLoader.from_env()
    except Exception:
        try:
            cfg = ConfigLoader.from_yaml(Path("config.yaml"))
        except Exception:
            cfg = PipelineConfig(input_dir=pdf.parent, output_dir=Path("./ocr_output"))
        ConfigLoader.apply_env_credentials(cfg)
    grobid_url: str = cfg.grobid_url

    try:
        engine = GrobidEngine(grobid_url=grobid_url)
        if not engine.health_check():
            return {
                "status": "error",
                "message": (
                    f"GROBID server not reachable at {grobid_url}. "
                    "Start with: docker run -p 8070:8070 lfoppiano/grobid:0.8.1"
                ),
            }

        metadata = await asyncio.to_thread(engine.extract_metadata, pdf, timeout_sec=120.0)

        return {
            "status": "ok",
            "title": metadata.title,
            "authors": metadata.authors,
            "doi": metadata.doi,
            "journal": metadata.journal,
            "volume": metadata.volume,
            "issue": metadata.issue,
            "year": metadata.year,
            "keywords": metadata.keywords,
            "abstract": metadata.abstract[:500] if metadata.abstract else "",
            "pages": metadata.pages,
        }
    except Exception as exc:
        logger.exception("ocr_metadata failed for %s", pdf_path)
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the OCR Pipeline MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
