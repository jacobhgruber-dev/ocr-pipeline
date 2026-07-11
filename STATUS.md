# OCR Pipeline — Project Status

Last updated: 2026-07-11

## Build

| Metric | Value |
|---|---|
| Tests | 408+ (baseline from 0.3.0; local Windows verify engines health True ×6) |
| Lint | ruff clean on changed engine/MCP files |
| Python | 3.10+ (CI: 3.10, 3.12) |
| Version | 0.3.0 (Beta) + Unreleased template/MCP fixes |
| License | MIT |
| CI | GitHub Actions (lint, type check, test on push/PR) |
| Docker | Dockerfile + docker-compose (GROBID) — optional |
| Git | main, direct push |

## Engines (7)

| Engine | Type | Free? | Best for | Template note |
|---|---|---|---|---|
| marker | Local (same venv OK) | ✅ | General OCR, prose | Auto-detect venv if `marker-pdf` importable |
| tesseract | Local binary | ✅ | Arabic/RTL, Cyrillic, fallback | Install OS package + language packs |
| mathpix | API | freemium | LaTeX math | `MATHPIX_APP_ID` / `MATHPIX_APP_KEY` |
| surya2 | Local (same venv OK) | ✅ | Multilingual + layout/tables | Auto-detect if `surya` importable |
| google_doc_ai | API | freemium | Forms | `GOOGLE_CLOUD_PROJECT` + ADC or `GOOGLE_API_KEY` |
| grobid | Docker | ✅ | Academic metadata | Optional; VLM metadata can substitute |
| trocr | Local | ✅ | Handwriting | Needs `transformers` + `torch`; health returns bool |

**VLM merge**: Gemini 2.5 Flash (default), Grok 4.3/4.5, Claude. Per-script routing in profiles (Grok for CJK/math/technical).

**ML table recognition**: Surya 2 TableRecPredictor (dual path with VLM-based table extraction).

## Supported Input Formats (30)

| Format | Source class | Extract text? | Render? | Metadata | Notes |
|---|---|---|---|---|---|
| PDF | `PdfSource` | ✅ PyMuPDF | ✅ fitz | GROBID/VLM | Existing pipeline path |
| Image | `ImageSource` | ❌ (OCR only) | ✅ self | EXIF | PNG/JPG/TIFF/WebP/BMP/HEIC; multi-page TIFF |
| EPUB | `EpubSource` | ✅ ebooklib | ✅ Calibre→PDF | OPF (DC) + Adobe DRM detection | Spine items = pages |
| DOCX | `DocxSource` | ✅ python-docx | ✅ LibreOffice→PDF | core_properties | Single page |
| TXT | `TxtSource` | ✅ charset-normalizer | ❌ | file stats | Encoding auto-detect |
| Markdown | `MarkdownSource` | ✅ charset-normalizer | ❌ | YAML frontmatter | Title, author, date, license |
| HTML | `HtmlSource` | ✅ lxml | ❌ | JSON-LD / meta tags | schema.org, citation_*, dc.* |
| LaTeX | `LatexSource` | ✅ regex | ❌ | \\title, \\author, \\abstract | Command stripping |
| JSON | `JsonSource` | ✅ built-in | ❌ | JSON-LD detection | .json, .jsonl support |
| RTF | `RtfSource` | ✅ striprtf | ❌ | file stats | Legacy legal docs |
| ODT | `OdtSource` | ✅ lxml/ZIP | ❌ | dc:* in meta.xml | OpenDocument, EU standard |
| Notebook | `NotebookSource` | ✅ built-in JSON | ❌ | kernel, lang, title | .ipynb cells + outputs |
| Archive | `ArchiveSource` | ✅ listing | ❌ | file count | ZIP/TAR/GZ/7z, readme extraction |
| Email | `EmailSource` | ✅ stdlib email | ❌ | From, To, Subject, Date | .eml + .mbox (multi-message) |
| Subtitles | `SubtitleSource` | ✅ text | ❌ | line count | .srt, .vtt — timestamp stripping |
| CSV/TSV | `CsvSource` | ✅ clevercsv | ❌ | dialect detection | Markdown table output |
| Excel | `ExcelSource` | ✅ calamine | ❌ | openpyxl props | One sheet = one page; .xlsx/.xls |
| PPTX | `PptxSource` | ✅ python-pptx | ✅ LibreOffice→PDF | core_properties | One slide = one page; speaker notes |
| DJVU | `DjvuSource` | ✅ djvutxt CLI | ✅ ddjvu CLI | page dimensions | Internet Archive, HathiTrust |
| Comics | `ComicSource` | ❌ (OCR only) | ✅ PIL | image count | .cbz (ZIP) + .cbr (RAR) |
| E-book | `EbookSource` | ❌ (DRM-blocked) | ❌ | DRM status, Calibre | .azw/.azw3/.kfx/.mobi; DeDRM detection |
| MARC | `MarcSource` | ✅ pymarc | ❌ | Title, author, ISBN, LCCN, subjects | Library catalog records |
| GIS | `GisSource` | ✅ JSON/pyshp | ❌ | Feature count, CRS, geometry types | .geojson, .shp |
| DXF | `DxfSource` | ✅ DXF parser | ❌ | Drawing title | TEXT/MTEXT entity extraction |
| SVG | `SvgSource` | ✅ lxml | ❌ | title/desc elements | Vector text extraction |
| Pages | `PagesSource` | ✅ lxml/ZIP | ❌ | document title | Apple Pages (modern format) |
| FB2 | `Fb2Source` | ✅ lxml | ❌ | Author, genre, ISBN, publisher, date | FictionBook e-books |
| TEI | `TeiSource` | ✅ lxml | ❌ | titleStmt, author, publisher, date | Scholarly editions |
| Audio | `MediaSource` | ✅ faster-whisper | ❌ | FFprobe + transcription | .mp3/.wav/.flac/.ogg; CPU Whisper |
| Video | `MediaSource` | ❌ (ffmpeg guide) | ❌ | FFprobe metadata | .mp4/.mkv/.avi/.mov/.webm |

**Rendering (format conversion)**: EPUB via Calibre ebook-convert, DOCX/PPTX via LibreOffice --headless.

**Handwriting recognition**: TrOCR (`microsoft/trocr-base-handwritten`) via `handwriting.py` — 3.42% CER on IAM, MIT license, text-line detection via Surya or EasyOCR, 8-bit quantization for CPU.

**Utilities**:
- `language_detect.py` — `detect_language(text)` via langdetect (55 languages, ISO 639-1)
- `sidecar.py` — `load_sidecar_metadata(path)` reads `{file}.meta.yaml`; `merge_sidecar_metadata()` fills empty fields only
- `identifier.py` — `resolve_doi()` (CrossRef API), `resolve_isbn()` (OpenLibrary API), `enrich_metadata()`
- `transcriber.py` — `transcribe_audio()` via faster-whisper (CPU, local, no API key)
- `file_guard.py` — `check_file_size()` with configurable thresholds (warn@500MB, refuse@2GB)
- `epub_images.py` — `extract_epub_images()` extracts embedded images from EPUB files
- `extractor.py` — `extract_page_images()` extracts embedded images from PDF pages

## Output Formats

| Format | Formatter | Extension | Notes |
|---|---|---|---|
| Markdown | `MarkdownFormatter` | `.md` | Primary output, YAML frontmatter |
| JSON | `JsonFormatter` | `.json` | Structured with blocks, bboxes, engine metadata |
| ALTO XML | `AltoFormatter` | `.xml` | v4.4 schema, word-level String+SP with WC confidence |
| hOCR | `HocrFormatter` | `.html` | XHTML with ocr_page/carea/par/line/word classes, x_wconf |

## Metadata Extraction Chain

```
format-native → sidecar (.meta.yaml) → VLM (Gemini) → GROBID → DOI/ISBN resolution
```

All stages run. Each only fills empty fields. Sidecar metadata never overrides extracted data. Identifier resolution queries CrossRef and OpenLibrary for DOIs/ISBNs found in metadata.

## Known Gaps

- Ground truth files exist (12 fixtures) but 11 are derived from pipeline output, not human-curated. Only `general_mixed_format.txt` has been manually curated.
- DOCX/EPUB image extraction: PDF implemented (`extract_page_images()`), EPUB implemented (`extract_epub_images()`), DOCX deferred.
- DOCX/PPTX rendering requires LibreOffice (`soffice --headless`) — clear install guidance when absent.
- Large-file guard warns at 500MB and refuses at 2GB. Streaming/chunked processing for >2GB files not implemented.
- NumPy mypy stub error is a pre-existing Python 3.14 environment issue, not project code.

## Session record (2026-07-11) — Windows host + MCP template hardening

### What was wrong in the published template (v0.3.0 clone)

| Failure mode | Root cause | Fix |
|---|---|---|
| Marker/Surya `unavailable: requires venv_path` | `create_engine` hard-required `marker_venv`; MCP often loads bare config (from_env fails; `config.yaml` only searched in CWD) | Auto-detect current venv when packages importable; MCP loads project-root config |
| Marker/Surya health = **`false`** (not unavailable) | Subprocess `find_spec` health under MCP timed out / false-negatived | In-process health when engine Python == `sys.executable` |
| TrOCR never loaded | `health_check` returned `None` on success; pipeline uses `if health_check()` | Return `bool` |
| TrOCR unknown engine | Missing factory branch | Register TrocrEngine in `create_engine` |
| Grok breaks after sync | `openai` not in `pyproject.toml` | Add dependency |
| Latin/Irish “unsupported” by Marker | Stale 40-lang hardcoded list | Import Surya’s 94-lang set |
| Profiles fail on Windows | `read_text()` without UTF-8 | Force `encoding="utf-8"` |
| Google Doc AI needs service account only | No API key path | `GOOGLE_API_KEY` via ClientOptions |
| Docs said empty `marker_venv` disables Marker | Wrong comment in config.example | Document auto-detect |

### What a fresh clone should do now

```bash
git clone https://github.com/jacobhgruber-dev/ocr-pipeline.git
cd ocr-pipeline
uv sync --extra marker   # or: uv pip install marker-pdf surya-ocr
cp config.example.yaml config.yaml
# Optional: system env vars for APIs (preferred over opencode env block)
uv run ocr-pipeline-mcp   # MCP: no marker_venv required if packages installed
```

Windows: use **CPU torch** if no CUDA (`uv pip install torch --index-url https://download.pytorch.org/whl/cpu`). First Marker/Surya page downloads HuggingFace models (slow once).

### Verified engine health (this host, bare PipelineConfig)

marker/surya2/tesseract/mathpix/google_doc_ai/trocr → **True**; grobid → False (Docker not running).

## Recent Work (2026-07-03 / 2026-07-04 session)

24 commits across two days:

| Phase | Commits | What |
|---|---|---|
| E2E + Benchmark + ALTO | 4 | Integration tests, ground truth, benchmark, ALTO XML output |
| Multi-format foundation | 3 | DocumentSource ABC, 8 core formats, extended metadata model |
| Format expansion | 3 | HTML, LaTeX, Markdown, JSON, RTF, ODT, Notebook, Archive, Email, Subtitles |
| DJVU + Comics + Language + Sidecar | 2 | Digital library formats, language detection, sidecar metadata |
| Identifier resolution | 1 | DOI→CrossRef, ISBN→OpenLibrary |
| Code review fixes | 3 | 43 bugs fixed across 4 code reviews |
| Architecture v0.3 | 2 | Design review + all 6 blocking issues fixed |
| Gap closure | 3 | CLI flag, hOCR, image extraction, ML table detection |
| Deferred features | 2 | Word-level bbox, streaming guard, stress tests, Sphinx docs |
| Pre-existing issues | 1 | README, config.yaml, deprecated comments — all current |
| EPUB/DOCX/PPTX rendering | 1 | Calibre + LibreOffice conversion pipeline |
| Audio transcription | 1 | faster-whisper CPU transcription |
| Handwriting + real fixtures + hardening | 2 | TrOCR engine, 8 real test files, XML entity bomb protection |
| macOS symlink + ebook-convert fix | 2 | Last platform bugs resolved |
