# Changelog

All notable changes to the OCR Pipeline will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — 2026-07-11

### Fixed (template / MCP usability — clone-and-run)

These bugs made a fresh clone or MCP-hosted run report Marker/Surya2 as
`unavailable` or `false` even when packages were installed:

- **`create_engine("marker"|"surya2")`**: auto-detect current venv when packages
  are importable; no longer hard-requires `marker_venv` in config.
- **MCP `ocr_status` / document tools**: load `config.yaml` from project root
  (not only CWD); seed `marker_venv` when packages live in this process.
- **Marker/Surya2 `health_check`**: prefer in-process `importlib` when engine
  Python == `sys.executable` (subprocess checks under MCP returned false negatives).
- **TrOCR `health_check`**: return `bool` True/False (was `None` on success →
  pipeline skipped TrOCR via `if engine.health_check()`).
- **TrOCR factory**: register constructor in `create_engine`.
- **Windows**: cross-platform venv python path (`Scripts/` vs `bin/`).
- **`MARKER_LANGUAGES`**: derive from Surya (94 langs) instead of stale 40-lang list
  (restored Latin `la` and Irish `ga`).
- **`read_text()` encoding**: UTF-8 on Windows for profiles, credentials, previews.
- **`ocr_pdf`**: restored as backward-compat alias for `ocr_document`.
- **Grok VLM**: add `openai` dependency; API key via system env (`XAI_API_KEY`).
- **Google Document AI**: support `GOOGLE_API_KEY` ClientOptions auth.

### Added
- Profiles `grok-value` / `grok-quality` and Grok model routing for CJK/math/technical.
- README VLM model selection tables from empirical Grok vs Gemini testing.

## [0.3.0] — 2026-07-04

### Added
- **30 input formats**: PDF, EPUB, DOCX, TXT, Markdown, HTML, LaTeX, JSON, RTF, ODT,
  Jupyter (.ipynb), CSV/TSV, Excel, PPTX, DJVU, Comics (.cbz/.cbr), Images (PNG/JPG/
  TIFF/WebP/BMP/HEIC), Archives (ZIP/TAR/GZ/7z), Email (.eml/.mbox), Subtitles (.srt/
  .vtt), E-books (.azw/.azw3/.kfx/.mobi), MARC (.mrc), GeoJSON/Shapefile, DXF, SVG,
  Apple Pages, FictionBook (.fb2), TEI XML, Audio/Video (FFprobe metadata).
- **DocumentSource ABC** with automatic format detection (extension + magic bytes).
- **Extended metadata model**: `SourceInfo`, `RightsInfo`, citation-ready fields.
- **Metadata extraction chain**: format-native → sidecar (.meta.yaml) → VLM → GROBID →
  DOI/ISBN resolution (CrossRef + OpenLibrary).
- **ALTO XML v4.4** output format for digital library compatibility.
- **hOCR output format** (XHTML with standard CSS classes).
- **Language auto-detection**: 55 languages via langdetect, ISO 639-1/639-3 mapping.
- **DRM detection**: AZW/AZW3/KFX/MOBI/EPUB Adobe DRM. Calibre ebook-convert integration
  for DRM-free files. DeDRM plugin detection.
- **PDF image extraction**: `extract_page_images()` via PyMuPDF.
- **ML table recognition**: Surya 2 TableRecPredictor integrated (dual path with VLM).
- **E2E integration tests**: stub VLM (CI-safe) and real VLM (API-key-gated).
- **Benchmark infrastructure**: 12 ground truth files + `scripts/benchmark.py` with CER/WER.
- **Identifier resolution**: DOI→CrossRef, ISBN→OpenLibrary. URL-prefix handling, 429 retry.
- **CLI `--input-extensions` flag**: multi-format globbing from the command line.
- **HEIC/HEIF image support** via pillow-heif.
- **TeiSource**: TEI XML scholarly editions with header metadata extraction.
- **Fb2Source**: FictionBook e-book format with full author name parsing.
- **PagesSource**: Apple Pages document extraction.
- **SvgSource**: SVG vector text extraction.

### Changed
- **CLI**: renamed from PDF-only to multi-format (examples say `./docs/`, not `./pdfs/`).
- **Pipeline**: `process_one()` accepts `Path` (auto-detect) or `DocumentSource`.
- **PageProcessor**: skips rendering for text-only formats, uses source image for images.
- **Document assembly**: un-gated from PDF-only — all 30 formats produce `document.md`.
- **page_count contract**: standardized across all 30 sources (int return, never raises).
- **Error handling**: `RenderError` consistency, bare `except Exception` replaced with logging.
- **pyproject.toml**: description and keywords updated for multi-format; Beta status.
- **EPUB/DOCX/PPTX rendering**: convert→PDF→render pipeline. EPUB via Calibre
  ebook-convert. DOCX/PPTX via LibreOffice --headless.
- **Audio/video**: MediaSource with FFprobe metadata. Audio transcription via
  faster-whisper (CPU, tiny model 39MB, 99 languages).
- **Large-file guard**: warn at 500 MB, refuse at 2 GB (configurable).
- **macOS compatibility**: `relative_to()` path resolution handles `/var` symlink.

### Fixed
- 42 bugs from 4 thorough code reviews (resource leaks, None guards, DRM false positives,
  XML entity bomb protection, Zip Slip path traversal, email mbox broken, JSON-LD detection,
  Excel TOCTOU data corruption, HEIF registration, and more).

## [0.2.0] — 2026-07-03

### Added
- **Script-aware model routing**: pipeline auto-detects page script (Cyrillic, CJK, Arabic, Greek)
  and routes to the correct VLM model (Gemini for most scripts, Claude Haiku for CJK).
- **6 universal document profiles**: general, academic, mathematical, legal, technical, books.
  Each with research-backed system prompts, few-shot examples, and script-aware model routing.
- **User-extensible profiles**: drop `.yaml` files into `profiles/` directory.
- **Tesseract OCR engine**: universal fallback, only working engine for Arabic RTL.
- **Surya2 OCR engine**: 91-language support, tested for Arabic/Cyrillic/Greek.
- **VLM-based metadata extraction**: extracts title, authors, document type, language, publisher,
  identifiers from any document type (academic, legal, book, technical, multilingual).
- **Per-page metadata comments**: `<!-- doc: "Title" | author: X | page: N -->` on every output page.
- **Cross-PDF concatenation**: `collection.md` assembled from all per-PDF `document.md` files.
- **Quality confidence scores**: per-page `<!-- OCR confidence: XX.X% -->` annotation.
- **Accuracy module**: CER/WER via Levenshtein distance.
- **Multi-language testing**: 24 PDFs across 9 scripts (Latin, Cyrillic, Greek, CJK, Arabic, etc.).
- **Engine comparison studies**: Marker vs Tesseract vs Mathpix vs Surya2 across all scripts.
- **GitHub Actions CI**: lint, type check, test on push/PR.
- **Docker support**: Dockerfile + docker-compose.yml with GROBID service.
- **Pre-commit hooks**: ruff + mypy.

### Changed
- **Profiles**: reduced from 7 to 6 universal profiles. Removed hyper-specific profiles
  (theological_journal, irish_hagiography, citation_focused) — merged into academic or provided
  as configurable custom profiles.
- **content_type → profile**: single concept, single `--profile` CLI flag.
- **Default VLM model**: `gemini-2.5-flash` (was `gemini-3.5-flash`).
- **Checkpoint v3**: per-PDF files instead of monolithic JSON (eliminates O(n²) I/O).
- **VLM prompts**: XML-structured, few-shot examples, anti-truncation rules, character-level formatting.
- **Mathematical profile**: best_model reverted to `gemini-2.5-flash` (Claude produced worse LaTeX).
- **Budget estimation**: `vlm_cost_per_call` corrected from 0.005 → 0.00015 (was 38x too high).

### Fixed
- **GROBID**: added missing `Accept: application/xml` header (was returning BibTeX, not XML).
- **Marker**: removed unsupported `languages` parameter from PdfConverter.
- **Tesseract**: added ISO 639-1 → ISO 639-2/T language code mapping (was silently using English).
- **Latin script detection**: fixed range that counted `[ ] ^ _` as Latin letters.
- **Unknown profile**: now logs warning instead of silent fallback to general.
- **VLM dispatcher**: warns on unknown model names instead of silent Anthropic routing.

### Removed
- `EngineName.OLMOCR` stub enum (no implementation).
- Dead `DEFAULT_SYSTEM_PROMPT` and unreachable guard in merger.
- Hyper-specific example profiles (theological_journal, irish_hagiography, citation_focused).

## [0.1.0] — Initial release

### Added
- Multi-engine OCR pipeline: Marker, Mathpix, Google Document AI, GROBID.
- VLM merge with Gemini and Claude support.
- Checkpoint/resume with SHA256 file identity.
- Budget tracking and cost estimation.
- Configurable post-processing pipeline.
- CLI and MCP server interfaces.
