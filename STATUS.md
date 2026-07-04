# OCR Pipeline — Project Status

Last updated: 2026-07-04

## Build

| Metric | Value |
|---|---|
| Tests | 408 passing (unit + integration + e2e + sources + language + sidecar + identifier + stress) |
| Lint | ruff clean (88 source + test + script files) |
| Format | ruff format clean (88 files) |
| Types | mypy pass on project code (1 pre-existing numpy stub issue, unrelated) |
| Python | 3.10+ (CI: 3.10, 3.12) |
| Version | 0.3.0 (Beta) |
| License | MIT |
| CI | GitHub Actions (lint, type check, test on push/PR) |
| Docker | Dockerfile + docker-compose (GROBID) |
| Git | 56 commits, direct to main |

## Engines (6)

| Engine | Type | Free? | Best for |
|---|---|---|---|
| marker | Local Python venv | ✅ | General OCR, prose |
| tesseract | Local binary | ✅ | Arabic/RTL, Cyrillic, universal fallback |
| mathpix | API (paid) | 1000 pg/mo free | LaTeX math, equations, Cyrillic |
| surya2 | Local Python venv | ✅ | 91 languages, Arabic, layout, table recognition |
| google_doc_ai | API (paid) | 500 pg/mo free | Forms, structured docs |
| grobid | Local Docker | ✅ | Academic metadata extraction |

**VLM merge**: Gemini 2.5 Flash (default), Claude Sonnet 5 (fallback). Script-aware model routing.

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
