# OCR Pipeline — Project Status

Last updated: 2026-07-03

## Build

| Metric | Value |
|---|---|
| Tests | 298 passing (unit + integration + e2e + sources) |
| Lint | ruff clean (56 source + test files) |
| Format | ruff format clean (56 files) |
| Types | mypy pass on project code (1 pre-existing numpy stub issue, unrelated) |
| Python | 3.10+ (CI: 3.10, 3.12) |
| Version | 0.2.0 |
| License | MIT |
| CI | GitHub Actions (lint, type check, test on push/PR) |
| Docker | Dockerfile + docker-compose (GROBID) |
| Git | 29 commits, direct to main |

## Profiles (6)

| Profile | Engines | Default Model | CJK Model | Rules |
|---|---|---|---|---|
| `general` | marker, tesseract, mathpix | gemini-2.5-flash | claude-haiku-4-5 | 13 |
| `academic` | marker, mathpix | gemini-2.5-flash | claude-haiku-4-5 | 15 |
| `mathematical` | mathpix, marker, tesseract | gemini-2.5-flash | claude-haiku-4-5 | 15 |
| `legal` | marker, mathpix, google_doc_ai | gemini-2.5-flash | claude-haiku-4-5 | 15 |
| `technical` | marker, mathpix, google_doc_ai | gemini-2.5-flash | claude-haiku-4-5 | 14 |
| `books` | marker, tesseract | gemini-2.5-flash | claude-haiku-4-5 | 17 |

All profiles include: few-shot examples, XML-structured prompts, anti-truncation, `[Header:]/[Footer:]` format, image text OCR. Script-aware routing auto-detects page script and routes CJK → Claude.

## Engines (6)

| Engine | Type | Free? | Best for |
|---|---|---|---|
| marker | Local Python venv | ✅ | General OCR, prose |
| tesseract | Local binary | ✅ | Arabic/RTL, Cyrillic, universal fallback |
| mathpix | API (paid) | 1000 pg/mo free | LaTeX math, equations, Cyrillic |
| surya2 | Local Python venv | ✅ | 91 languages, Arabic, layout |
| google_doc_ai | API (paid) | 500 pg/mo free | Forms, structured docs |
| grobid | Local Docker | ✅ | Academic metadata extraction |

## Supported Input Formats (11)

| Format | Source class | Extract text? | Render to image? | Metadata | Notes |
|---|---|---|---|---|---|
| PDF | `PdfSource` | ✅ PyMuPDF | ✅ fitz | GROBID/VLM | Existing pipeline path |
| Image | `ImageSource` | ❌ (OCR only) | ✅ self | EXIF | PNG/JPG/TIFF/WebP/BMP; multi-page TIFF |
| EPUB | `EpubSource` | ✅ ebooklib | ❌ | OPF (DC) | One spine item = one page |
| DOCX | `DocxSource` | ✅ python-docx | ❌ | core_properties | Single page |
| TXT | `TxtSource` | ✅ charset-normalizer | ❌ | file stats | Encoding auto-detect |
| Markdown | `MarkdownSource` | ✅ charset-normalizer | ❌ | YAML frontmatter | Title, author, date, license |
| HTML | `HtmlSource` | ✅ lxml | ❌ | JSON-LD / meta tags | schema.org, citation_*, dc.* |
| LaTeX | `LatexSource` | ✅ regex | ❌ | \\title, \\author, \\abstract | Command stripping |
| CSV/TSV | `CsvSource` | ✅ clevercsv | ❌ | dialect detection | Markdown table output |
| Excel | `ExcelSource` | ✅ calamine | ❌ | openpyxl props | One sheet = one page; .xlsx/.xls |
| PPTX | `PptxSource` | ✅ python-pptx | ❌ | core_properties | One slide = one page; speaker notes |

**Detect**: `detect_source(path)` factory — extension first, magic bytes fallback. `ConfigError` for unsupported types.

## Architecture Decisions

1. **Script-aware model routing** — `_detect_script()` + `model_routing` dict per profile. CJK → Claude Haiku, everything else → Gemini.
2. **Profiles as single source of truth** — `profiles.py` eliminated duplicate prompt system (211 lines removed from merger.py).
3. **content_type merged into profile** — single concept, single `--profile` CLI flag.
4. **Checkpoint v3** — Per-PDF files instead of monolithic JSON. Eliminates O(n²) I/O.
5. **Research-backed prompts** — XML tags, few-shot examples, anti-truncation, character-level formatting.

## Critical Finding: Script-Dependent Model Behavior

| Script | Gemini 2.5 Flash | Claude Haiku 4-5 | Routed To |
|---|---|---|---|
| Latin + diacritics | ✅ Perfect | — | Gemini |
| Cyrillic | ✅ Perfect | — | Gemini |
| Greek (polytonic) | ✅ Perfect | — | Gemini |
| CJK | ❌ Garbled | ✅ Perfect | Claude Haiku |
| Arabic RTL | Engine-dep. | — | Tesseract/Surya2 |
| LaTeX math | ✅ With prompts | — | Gemini |

## Known Gaps

- Table detection is prompt-based (VLM) — no dedicated ML model for cell-level extraction.
- Image handling is placeholder-based (`[Figure: description]`) — no embedded image extraction.
- Ground truth files exist (12 fixtures) but 11 are derived from pipeline output, not human-curated. Only `general_mixed_format.txt` has been manually curated from the Wikipedia source.
- ALTO XML output uses block-level granularity — word-level bounding boxes would require engine changes (only Surya2 produces blocks, and only at layout level).
- No hOCR output format (lower priority than ALTO; Tesseract can natively produce it if needed).

## Recent Work (2026-07-03 session)

3 commits from this session:

| Commit | What |
|---|---|
| `eb452ad` | E2E integration tests (stub + real VLM), 12 ground truth files, benchmark script |
| `28c0f2a` | ALTO XML v4.4 output format (AltoFormatter, page dimension capture, lxml) |
| `a0fab5b` | Bug fixes: Pillow resource leak, negative bbox clamp, None text guard, extractable-text dimensions, ruff format pass, curated ground truth fix |

## Shipping Infrastructure

| Item | Status |
|---|---|
| GitHub Actions CI | ✅ Lint + type check + test on push/PR |
| Docker | ✅ Dockerfile + docker-compose (GROBID) |
| Pre-commit hooks | ✅ ruff + mypy |
| CHANGELOG.md | ✅ v0.2.0 |
| SECURITY.md | ✅ Vulnerability reporting + API privacy |
| py.typed (PEP 561) | ✅ |
| License (MIT) | ✅ |
| E2E tests (stub + real VLM) | ✅ `pytest -m e2e` — stub runs in CI, real VLM needs API key |
| Benchmark (12 fixtures) | ✅ `scripts/benchmark.py` — CER/WER against ground truth |
| Ground truth files (12) | ✅ `tests/fixtures/ground_truth/` — baselines from marker+gemini output |
| ALTO XML output | ✅ `output_formats: ["markdown", "json", "alto"]` — v4.4 schema, lxml-valid, word-level confidence |
| Ruff formatting | ✅ 47/47 files clean (`ruff format` pass) |
| Code review | ✅ Passed — 4 bugs found and fixed, zero regressions |
