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
from .pipeline import Pipeline

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

    engine_list = [e.strip() for e in engines.split(",") if e.strip()]
    lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]

    # Try env-based config first (picks up marker_venv, credentials, etc.)
    try:
        cfg = ConfigLoader.from_env()
    except Exception:
        cfg = PipelineConfig(input_dir=pdf.parent, output_dir=out)

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
    vlm_model: str = "gemini-3.5-flash",
    vlm_enabled: bool = True,
    content_type: str = "general",
    languages: str = "en",
    test_mode: bool = False,
) -> dict[str, Any]:
    """OCR a PDF file through the full pipeline and return extracted markdown.

    Processes the PDF through render → multi-engine OCR → VLM merge,
    producing per-page markdown files in the output directory.

    Args:
        pdf_path: Absolute path to the PDF file.
        output_dir: Directory for output files (default: ./ocr_output/).
        engines: Comma-separated engine names (marker, mathpix, surya2, google_doc_ai).
        vlm_model: VLM model for merge (gemini-3.5-flash, claude-sonnet-4-6, etc.).
        vlm_enabled: Whether to use VLM to merge engine outputs.
        content_type: Document type hint (general, theological, academic, mathematical).
        languages: Comma-separated language codes (en, de, fr, la, grc, he, etc.).
        test_mode: If True, process only the first 3 pages.
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
        stats = await asyncio.to_thread(
            pipeline.process_one, Path(pdf_path).resolve()
        )

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
) -> dict[str, Any]:
    """OCR a single page image using a specific engine.

    Args:
        image_path: Absolute path to a PNG or JPEG image of a document page.
        engine: OCR engine to use (marker, mathpix, surya2, google_doc_ai).
    """
    img = Path(image_path).resolve()
    if not img.is_file():
        return {"status": "error", "message": f"Image not found: {image_path}"}

    # Load config for engine parameters (marker_venv, credentials, etc.)
    try:
        cfg = ConfigLoader.from_env()
    except Exception:
        cfg = PipelineConfig(
            input_dir=img.parent, output_dir=Path("./ocr_output")
        )

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
async def ocr_status() -> dict[str, Any]:
    """Check which OCR engines are available and their health status."""
    engine_names = ["marker", "mathpix", "surya2", "google_doc_ai", "grobid"]
    statuses: dict[str, bool | str] = {}

    # Load config to pick up any env-configured engine settings
    try:
        cfg = ConfigLoader.from_env()
    except Exception:
        cfg = PipelineConfig(
            input_dir=Path("."), output_dir=Path("./ocr_output")
        )

    for name in engine_names:
        try:
            engine_inst = create_engine(name, cfg)
            ok = engine_inst.health_check()
            statuses[name] = ok
        except Exception as exc:
            statuses[name] = f"unavailable: {exc}"

    return {"engines": statuses}


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the OCR Pipeline MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
