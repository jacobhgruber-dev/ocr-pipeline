"""MCP server for OCR Pipeline — exposes OCR tools to opencode agents.

Multi-format aware: 30 input formats, 7 engines, handwriting, audio transcription.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import ConfigLoader, PipelineConfig
from .engines import create_engine
from .languages import ENGINE_NAMES, LANGUAGE_NAMES, list_languages_for_engine
from .models import MetadataResult
from .pipeline import Pipeline
from .profiles import PROFILES, get_profile, list_profiles
from .sources import detect_source

logger = logging.getLogger("ocr-pipeline-mcp")

mcp = FastMCP(
    "ocr-pipeline",
    instructions=(
        "OCR Pipeline MCP — multi-engine OCR for documents, images, audio, and handwriting.\n\n"
        "Tools:\n"
        "- ocr_document: Process any supported file (PDF, EPUB, DOCX, image, etc.)\n"
        "- ocr_page: OCR a single page image with a specific engine\n"
        "- ocr_handwriting: Recognize handwriting in an image (TrOCR)\n"
        "- ocr_transcribe: Transcribe audio to text (Whisper)\n"
        "- ocr_metadata: Extract metadata from any supported document\n"
        "- ocr_status: Check engine health and availability\n"
        "- ocr_profiles: List available document profiles\n"
        "- ocr_languages: List supported language codes\n"
        "- ocr_formats: List supported input formats\n"
        "- ocr_detect: Detect file type and preview processing"
    ),
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_SUPPORTED_FORMATS = {
    "pdf": "PDF document",
    "epub": "EPUB e-book",
    "docx": "Word document",
    "txt": "Plain text",
    "md": "Markdown",
    "html": "HTML page",
    "tex": "LaTeX source",
    "json": "JSON data",
    "rtf": "Rich Text Format",
    "odt": "OpenDocument Text",
    "csv": "CSV spreadsheet",
    "tsv": "TSV spreadsheet",
    "xlsx": "Excel spreadsheet",
    "pptx": "PowerPoint",
    "png": "PNG image",
    "jpg": "JPEG image",
    "jpeg": "JPEG image",
    "tiff": "TIFF image",
    "webp": "WebP image",
    "bmp": "BMP image",
    "heic": "HEIC image",
    "djvu": "DJVU scanned book",
    "cbz": "Comic archive (ZIP)",
    "cbr": "Comic archive (RAR)",
    "azw": "Kindle e-book",
    "mobi": "Mobipocket e-book",
    "eml": "Email message",
    "mbox": "Email mailbox",
    "srt": "Subtitle (SRT)",
    "vtt": "Subtitle (WebVTT)",
    "zip": "ZIP archive",
    "tar": "TAR archive",
    "gz": "Gzip compressed",
    "7z": "7-Zip archive",
    "ipynb": "Jupyter notebook",
    "geojson": "GeoJSON",
    "shp": "Shapefile",
    "dxf": "CAD drawing",
    "svg": "SVG graphic",
    "pages": "Apple Pages",
    "fb2": "FictionBook",
    "mrc": "MARC record",
    "mp3": "MP3 audio",
    "wav": "WAV audio",
    "flac": "FLAC audio",
    "mp4": "MP4 video",
    "mkv": "Matroska video",
}


def _load_config(pdf_path: str, output_dir: str, engines: str, vlm_model: str, vlm_enabled: bool, languages: str, test_mode: bool, profile_name: str = "") -> PipelineConfig:
    pdf = Path(pdf_path).resolve()
    if not pdf.is_file():
        raise ValueError(f"File not found: {pdf_path}")
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    try:
        cfg = ConfigLoader.from_env()
    except Exception:
        try:
            cfg = ConfigLoader.from_yaml(Path("config.yaml"))
        except Exception:
            cfg = PipelineConfig(input_dir=pdf.parent, output_dir=out)
        ConfigLoader.apply_env_credentials(cfg)

    _default_engines = "marker"
    _default_vlm_model = "gemini-2.5-flash"
    _default_languages = "en"
    if profile_name:
        profile = get_profile(profile_name)
        if engines == _default_engines:
            engines = ",".join(profile.suggested_engines)
        if vlm_model == _default_vlm_model:
            vlm_model = profile.suggested_model
        if languages == _default_languages:
            languages = ",".join(profile.suggested_languages)

    engine_list = [e.strip() for e in engines.split(",") if e.strip()]
    lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]
    cfg.input_dir = pdf.parent
    cfg.output_dir = out
    cfg.engines = engine_list
    cfg.vlm_model = vlm_model
    cfg.vlm_enabled = vlm_enabled
    cfg.profile = profile_name if profile_name else "general"
    cfg.languages = lang_list
    cfg.test_mode = test_mode
    return cfg


def _find_output_preview(output_dir: Path, max_chars: int = 2000) -> str:
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


def _metadata_to_response(metadata: MetadataResult) -> dict[str, Any]:
    return {
        "status": "ok",
        "title": metadata.title,
        "authors": metadata.authors,
        "doi": metadata.doi,
        "isbn": metadata.isbn,
        "journal": metadata.journal,
        "publisher": metadata.publisher,
        "volume": metadata.volume,
        "issue": metadata.issue,
        "year": metadata.year,
        "date": metadata.date,
        "keywords": metadata.keywords,
        "abstract": metadata.abstract[:500] if metadata.abstract else "",
        "pages": metadata.pages,
        "document_type": metadata.document_type,
        "language": metadata.language,
        "extraction_method": metadata.extraction_method,
    }


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def ocr_document(
    file_path: str,
    output_dir: str | None = None,
    engines: str = "marker",
    vlm_model: str = "gemini-2.5-flash",
    vlm_enabled: bool = True,
    languages: str = "en",
    test_mode: bool = False,
    profile_name: str = "",
) -> dict[str, Any]:
    """Process any supported document through the OCR pipeline.

    Handles 30+ formats: PDF, EPUB, DOCX, images, Markdown, HTML,
    LaTeX, CSV, Excel, PPTX, e-books, email, subtitles, archives,
    audio, video, and more.  Auto-detects format.

    Text-based formats (EPUB, DOCX, Markdown) skip OCR entirely and
    extract text directly.  Images and PDFs go through multi-engine
    OCR → VLM merge.

    Args:
        file_path: Absolute path to the file.
        output_dir: Directory for output (default: ./ocr_output/).
        engines: Comma-separated engine names (marker, tesseract, mathpix, surya2, google_doc_ai, trocr).
        vlm_model: VLM model for merge.
        vlm_enabled: Whether to use VLM merge.
        languages: Comma-separated language codes.
        test_mode: Process only first 3 pages.
        profile_name: Document profile (auto-fills engines, model, languages).
    """
    output_dir = output_dir or "./ocr_output"

    try:
        cfg = _load_config(file_path, output_dir, engines, vlm_model, vlm_enabled, languages, test_mode, profile_name=profile_name)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": f"Config error: {exc}"}

    # Detect format
    fp = Path(file_path).resolve()
    try:
        source = detect_source(fp)
        fmt = source.source_format
    except Exception:
        fmt = "unknown"

    try:
        pipeline = Pipeline(cfg)
        if not pipeline.engines:
            return {"status": "error", "message": f"No OCR engines available from [{engines}]."}

        stats = await asyncio.to_thread(pipeline.process_one, fp)
        text_preview = _find_output_preview(cfg.output_dir)

        return {
            "status": "ok",
            "format": fmt,
            "pages_processed": stats.get("pages_processed", 0),
            "pages_complete": stats.get("pages_complete", 0),
            "pages_failed": stats.get("pages_failed", 0),
            "output_dir": str(cfg.output_dir),
            "text_preview": text_preview[:3000] if text_preview else "",
        }
    except Exception as exc:
        logger.exception("ocr_document failed for %s", file_path)
        return {"status": "error", "message": str(exc)}


@mcp.tool()
async def ocr_page(
    image_path: str,
    engine: str = "marker",
    languages: str = "en",
) -> dict[str, Any]:
    """OCR a single page image using a specific engine.

    Args:
        image_path: Absolute path to a PNG or JPEG image.
        engine: OCR engine (marker, tesseract, mathpix, surya2, google_doc_ai, trocr).
        languages: Comma-separated language codes.
    """
    img = Path(image_path).resolve()
    if not img.is_file():
        return {"status": "error", "message": f"Image not found: {image_path}"}

    lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]

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
        return {"status": "error", "message": f"Engine '{engine}' health check failed."}

    try:
        t0 = time.perf_counter()
        result = await asyncio.to_thread(engine_instance.recognize, img, 0, cfg.api_timeout_sec, lang_list)
        duration = round(time.perf_counter() - t0, 2)

        if result.error:
            return {"status": "error", "engine": engine, "message": result.error, "duration_sec": duration}

        return {"text": result.text, "engine": engine, "duration_sec": duration, "confidence": getattr(result, "confidence", None)}
    except Exception as exc:
        logger.exception("ocr_page failed for %s", image_path)
        return {"status": "error", "engine": engine, "message": str(exc)}


@mcp.tool()
async def ocr_handwriting(image_path: str) -> dict[str, Any]:
    """Recognize handwriting in an image using TrOCR.

    Uses Microsoft's TrOCR model (3.42% CER on IAM benchmark).
    Works on CPU.  First use downloads the model (~350 MB).

    Args:
        image_path: Absolute path to a PNG or JPEG image with handwriting.
    """
    img = Path(image_path).resolve()
    if not img.is_file():
        return {"status": "error", "message": f"Image not found: {image_path}"}

    try:
        from .handwriting import recognize_handwriting

        t0 = time.perf_counter()
        full_text, line_results = await asyncio.to_thread(recognize_handwriting, img)
        duration = round(time.perf_counter() - t0, 2)

        return {
            "status": "ok",
            "text": full_text,
            "lines_detected": len(line_results),
            "lines": [{"text": ln["text"], "confidence": ln.get("confidence", 0)} for ln in line_results[:20]],
            "duration_sec": duration,
        }
    except ImportError:
        return {"status": "error", "message": "TrOCR not available. Install: pip install transformers torch"}
    except Exception as exc:
        logger.exception("ocr_handwriting failed")
        return {"status": "error", "message": str(exc)}


@mcp.tool()
async def ocr_transcribe(audio_path: str) -> dict[str, Any]:
    """Transcribe audio to text using Whisper (faster-whisper).

    Uses the tiny model (39 MB) on CPU.  First use downloads the model.
    Supports MP3, WAV, FLAC, OGG, and other formats.
    99 languages auto-detected.  VAD removes silence.

    Args:
        audio_path: Absolute path to an audio file.
    """
    path = Path(audio_path).resolve()
    if not path.is_file():
        return {"status": "error", "message": f"Audio file not found: {audio_path}"}

    try:
        from .transcriber import transcribe_audio

        t0 = time.perf_counter()
        text = await asyncio.to_thread(transcribe_audio, path)
        duration = round(time.perf_counter() - t0, 2)

        if not text.strip():
            return {"status": "ok", "text": "", "note": "No speech detected or transcription produced empty text.", "duration_sec": duration}

        return {"status": "ok", "text": text[:10000], "char_count": len(text), "duration_sec": duration}
    except ImportError:
        return {"status": "error", "message": "faster-whisper not available. Install: pip install faster-whisper"}
    except Exception as exc:
        logger.exception("ocr_transcribe failed")
        return {"status": "error", "message": str(exc)}


@mcp.tool()
async def ocr_formats() -> dict[str, Any]:
    """List supported input formats that the pipeline can process."""
    return {"formats": [{"extension": k, "description": v} for k, v in sorted(_SUPPORTED_FORMATS.items())], "count": len(_SUPPORTED_FORMATS)}


@mcp.tool()
async def ocr_detect(file_path: str) -> dict[str, Any]:
    """Detect file type and preview what the pipeline would do.

    Reports: format, page count, whether text extraction is possible,
    whether rendering is available, and what OCR engines would run.

    Args:
        file_path: Absolute path to the file.
    """
    fp = Path(file_path).resolve()
    if not fp.is_file():
        return {"status": "error", "message": f"File not found: {file_path}"}

    try:
        source = detect_source(fp)
        return {
            "status": "ok",
            "format": source.source_format,
            "mimetype": source.source_mimetype,
            "page_count": source.page_count,
            "has_text_extraction": getattr(source, "has_text_extraction", None),
            "has_rendering": getattr(source, "has_rendering", None),
            "has_native_metadata": getattr(source, "has_native_metadata", None),
            "file_size_bytes": fp.stat().st_size,
        }
    except Exception as exc:
        return {"status": "error", "message": f"Unsupported or unreadable file: {exc}"}


@mcp.tool()
async def ocr_profiles() -> dict[str, Any]:
    """List available document profiles with engine recommendations."""
    result = []
    for profile in PROFILES.values():
        result.append({
            "name": profile.name,
            "description": profile.description,
            "suggested_engines": profile.suggested_engines,
            "optional_engines": profile.optional_engines,
            "suggested_languages": profile.suggested_languages,
            "suggested_model": profile.suggested_model,
        })
    return {"profiles": result}


@mcp.tool()
async def ocr_status() -> dict[str, Any]:
    """Check which OCR engines are available and their health status."""
    engine_names = ["marker", "tesseract", "mathpix", "surya2", "google_doc_ai", "grobid", "trocr"]
    statuses: dict[str, bool | str] = {}

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
        "vlm_models_available": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "claude-haiku-4-5", "claude-sonnet-5"],
    }


@mcp.tool()
async def ocr_languages(engine: str | None = None) -> dict[str, Any]:
    """List supported language codes and their names."""
    if engine is not None:
        if engine not in ENGINE_NAMES:
            return {"status": "error", "message": f"Unknown engine: {engine!r}. Valid: {', '.join(sorted(ENGINE_NAMES.keys()))}"}
        try:
            codes = list_languages_for_engine(engine)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        langs = [{"code": code, "name": LANGUAGE_NAMES.get(code, code)} for code in codes]
        return {"languages": langs, "engine": engine, "count": len(langs)}

    langs = [{"code": code, "name": name} for code, name in LANGUAGE_NAMES.items()]
    langs.sort(key=lambda x: x["code"])
    return {"languages": langs, "count": len(langs)}


@mcp.tool()
async def ocr_metadata(file_path: str) -> dict[str, Any]:
    """Extract metadata from any supported document using the full chain.

    Chain: format-native → sidecar (.meta.yaml) → VLM → GROBID → DOI/ISBN resolution.
    Works with PDF, EPUB, DOCX, HTML, Markdown, and all other formats.

    Args:
        file_path: Absolute path to the document.
    """
    fp = Path(file_path).resolve()
    if not fp.is_file():
        return {"status": "error", "message": f"File not found: {file_path}"}

    try:
        cfg = ConfigLoader.from_env()
    except Exception:
        try:
            cfg = ConfigLoader.from_yaml(Path("config.yaml"))
        except Exception:
            cfg = PipelineConfig(input_dir=fp.parent, output_dir=Path("./ocr_output"))
        ConfigLoader.apply_env_credentials(cfg)

    # Try format-native metadata first (works for all 30 formats)
    try:
        source = detect_source(fp)
        if source.source_format != "pdf":
            try:
                meta = source.extract_metadata()
                if meta.title or meta.authors:
                    return _metadata_to_response(meta)
            except Exception:
                pass
    except Exception:
        pass

    # VLM → GROBID fallback (PDF-specific)
    if fp.suffix.lower() == ".pdf":
        try:
            from .engines.metadata_vlm import VlmMetadataEngine

            vlm = VlmMetadataEngine(vlm_model=cfg.vlm_metadata_model, api_key=cfg.gemini_api_key, page_count=3)
            vlm_result = await asyncio.to_thread(vlm.extract, fp)
            if vlm_result.extraction_method == "vlm" and (vlm_result.title or vlm_result.document_type):
                return _metadata_to_response(vlm_result)
        except Exception as exc:
            logger.warning("VLM metadata failed: %s", exc)

        try:
            from .engines.grobid import GrobidEngine

            engine = GrobidEngine(grobid_url=cfg.grobid_url)
            if engine.health_check():
                metadata = await asyncio.to_thread(engine.extract_metadata, fp, timeout_sec=120.0)
                metadata.extraction_method = "grobid"
                return _metadata_to_response(metadata)
        except Exception as exc:
            logger.warning("GROBID metadata failed: %s", exc)

    return {"status": "error", "message": "Metadata extraction failed (no available method)"}


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the OCR Pipeline MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
