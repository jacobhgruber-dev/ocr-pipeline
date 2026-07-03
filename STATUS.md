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
| `mathematical` | mathpix, marker | gemini-2.5-flash | 15 | LaTeX math, \mathbb/\mathcal, theorems, matrices, statistical tables |
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

- **12 English-language PDFs** from public domain sources (all 6 profiles). See `tests/fixtures/SOURCES.md`.
- **5 multilingual PDFs** from Anna's Archive: Greek (Aristotle), French (Hugo), Russian (math), Chinese (ML), English (topology). See `tests/fixtures/multilingual/`.
- All 12 English fixtures tested with gemini-2.5-flash: **0 failures**.
- All 5 multilingual fixtures tested with gemini-2.5-flash AND claude-sonnet-5: **script-dependent results**.

## Critical Finding: Script-Dependent Model Behavior

Multi-language testing revealed that **no single VLM model handles all scripts**. Model selection is not a cost/quality tradeoff — it's a correctness question:

| Script | Gemini 2.5 Flash | Claude Sonnet 5 |
|---|---|---|
| **Latin + diacritics** (French éèêàôîç) | ✅ Perfect | ✅ Good |
| **Greek** (polytonic άέήίόύώ) | ✅ Perfect | Not tested |
| **Cyrillic** (Russian Глава, §, ∃) | ✅ Perfect (3245 chars) | ❌ Catastrophic — replaces with Latin lookalikes (1859 chars) |
| **CJK** (Chinese 目录, 判定问题) | ❌ Total failure — garbled Latin | ✅ Flawless (3808 chars) |
| **Math LaTeX** ($\mathbb{R}$, $\gamma$) | ✅ With improved prompts | ⚠️ Prefers Unicode (γ) over LaTeX ($\gamma$) |

### Product Implications

1. **Script-aware model routing is essential.** Profiles should not blindly recommend one model. The pipeline needs to detect the dominant script of each page and route to the appropriate model:
   - Cyrillic/diacritic-heavy Latin → Gemini (Claude destroys Cyrillic)
   - CJK → Claude (Gemini fails entirely)
   - Greek → Gemini
   - Plain Latin → Either, prefer cheaper Gemini

2. **Mathematical profile fixed — uses Gemini**, not Claude. Gemini 2.5 Flash with our improved prompts produces better LaTeX output for OCR transcription than Claude (which defaults to Unicode math characters for transcription).

3. **Google Doc AI tested and verified.** Adds better table column alignment, sub/superscript preservation, footer text capture, and header separation. Worth keeping as a suggested engine for legal and technical profiles. At $0.0015/page with 500 free pages/month — effectively free.

4. **Research-backed prompt improvements work.** Testing confirmed that few-shot examples, XML tags, anti-truncation rules, and character-level formatting instructions dramatically improve VLM output across all profiles and models.

## What We Learned

| Finding | Source | Action Taken |
|---|---|---|
| Gemini produces excellent LaTeX with good prompts | Math theorem page — full `$\mathbb{R}$`, `$\square$`, `$\gamma$` | Kept Gemini as default for mathematical profile |
| Claude destroys Cyrillic (replaces with Latin lookalikes) | Russian math book — 0 Cyrillic chars, all garbled | Documented script-dependent behavior in README |
| Gemini fails on Chinese (garbled Latin) | Chinese ML book — 0 CJK ideographs | Documented Claude as only option for CJK |
| Few-shot examples fix format adherence | Books test — all 6 attributions preserved (`—Plato`, `—MONTAIGNE`) | Applied to all 6 profiles |
| Anti-truncation rules work | Academic test — Gemini stopped at 330 tokens before fix | Added `<completeness>` section to all prompts |
| Character-level instructions beat visual descriptions | Legal test — "wrap in *asterisks*" vs "use italic" | Rewrote all italic rules |
| Google Doc AI adds structural precision | Legal + Technical fixtures — better tables, headers, subs | Kept as optional suggestion with credential note |
| Marker's `languages` parameter was broken | All image-only PDFs failed | Removed unsupported kwarg; language hints go to VLM only |

## Architecture Decisions

1. **Profiles as single source of truth** — `profiles.py` eliminated duplicate prompt system in `merger.py` (~211 lines removed)
2. **Model default budget-safe** — `suggested_model()` always returns gemini-2.5-flash (free tier); `best_model()` for Claude upgrades
3. **content_type merged into profile** — single concept, single CLI flag (`--profile`)
4. **Parallel PDF processing** — `pdf_concurrency` (default 2) processes multiple PDFs simultaneously
5. **Research-backed prompts** — few-shot examples, XML tags, anti-truncation, character-level formatting instructions based on Anthropic/Google official docs

## Known Gaps

- **Script-aware model routing not implemented** — profiles recommend a single model, but multi-language testing shows catastrophic failures when the wrong model meets the wrong script
- Table detection is prompt-based (VLM) — no dedicated ML model
- Image handling is placeholder-based — no embedded image extraction
- Progress bar counts PDFs not pages (display limitation, total pages logged at start)
- Marker's `languages` parameter removed — installed version doesn't support it; language hints go to VLM only

## Recent Changes

See `git log` for full history. Key commits:
- `66af62a` — Restore Google Doc AI as optional suggestion (tested and verified)
- `6daa80a` — Fix mathematical profile best_model to gemini-2.5-flash (test evidence)
- `53781f6` — Fix Marker languages bug + 5 multilingual test fixtures
- `87f9cd3` — Research-backed prompt improvements + 12 real test PDFs
- `9793ac6` — 7→6 universal profiles, remove content_type, user-extensible profiles
- `810ddec` — Cross-PDF concatenation, quality confidence scores, table+figure prompts
