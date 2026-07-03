# Changelog

All notable changes to the OCR Pipeline will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — Unreleased

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
