# OCR Pipeline — Project Status

Last updated: 2026-07-02

## Build

| Metric | Value |
|---|---|
| Tests | 238 passing (unit), 0 failing |
| Lint | ruff clean (27 source files) |
| Types | mypy clean (27 source files) |
| Python | 3.12+ |
| License | MIT |

## Profiles (6)

| Profile | Engines | Model | Rules | Description |
|---|---|---|---|---|
| `general` | marker | gemini-2.5-flash | 13 | Catch-all: tables, figures, multi-column, headers, lists, code |
| `academic` | marker, mathpix | gemini-2.5-flash | 15 | Citations (all styles), DOIs, abstracts, affiliations, LaTeX in papers |
| `mathematical` | mathpix, marker | **claude-sonnet-5** | 15 | LaTeX math, \mathbb/\mathcal, theorems, matrices, statistical tables |
| `legal` | marker, google_doc_ai | gemini-2.5-flash | 15 | § symbols, case citations, paragraph hierarchy, signature blocks |
| `technical` | marker, google_doc_ai | gemini-2.5-flash | 14 | Callout boxes, tolerances, BOMs, code blocks, revision tables |
| `books` | marker | gemini-2.5-flash | 17 | Front/back matter, TOC/index, dialogue, scene breaks, Roman numerals |

All profiles include: few-shot examples, XML-structured prompts, anti-truncation rules, [Header:]/[Footer:] bracketed format, image text OCR.

User-extensible: custom profiles load from `profiles/*.yaml` (3 examples provided).

## Engines (5)

| Engine | Type | Free? | Best for |
|---|---|---|---|
| marker | Local Python venv | ✅ | General OCR, prose |
| mathpix | API (paid) | 1000 pg/mo free | LaTeX math, equations |
| surya2 | Local Python venv | ✅ | 91 languages, layout |
| google_doc_ai | API (paid) | 500 pg/mo free | Forms, structured docs |
| grobid | Local Docker | ✅ | Metadata extraction |

## Language Support

- 53 ISO 639-1 codes in registry with human-readable names
- Fuzzy-matching validation (typing "irish" warns "Did you mean 'gle'?")
- Per-engine language support: marker (41), surya2 (all 53), google_doc_ai (51)

## Test Fixtures

12 real-world PDFs from public domain sources across all 6 profiles. See `tests/fixtures/SOURCES.md`.

## Architecture Decisions

1. **Profiles as single source of truth** — `profiles.py` eliminated duplicate prompt system in `merger.py` (~211 lines removed)
2. **Model default budget-safe** — `suggested_model()` always returns gemini-2.5-flash (free tier); `best_model()` for Claude upgrades
3. **content_type merged into profile** — single concept, single CLI flag (`--profile`)
4. **Parallel PDF processing** — `pdf_concurrency` (default 2) processes multiple PDFs simultaneously
5. **Research-backed prompts** — few-shot examples, XML tags, anti-truncation, character-level formatting instructions based on Anthropic/Google official docs

## Known Gaps

- Table detection is prompt-based (VLM) — no dedicated ML model
- Image handling is placeholder-based — no embedded image extraction
- Progress bar counts PDFs not pages (display limitation, total pages logged at start)
- No before/after integration test results yet — fixtures collected, pending pipeline run

## Recent Changes

See `git log` for full history. Key commits:
- `87f9cd3` — Research-backed prompt improvements + 12 real test PDFs
- `9793ac6` — 7→6 universal profiles, remove content_type, user-extensible profiles
- `810ddec` — Cross-PDF concatenation, quality confidence scores, table+figure prompts
- `cbfc368` — Parallel PDF processing + page-aware progress
