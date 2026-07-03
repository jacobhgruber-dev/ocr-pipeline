# OCR Pipeline — Project Status

Last updated: 2026-07-03

## Build

| Metric | Value |
|---|---|
| Tests | 249 passing (unit + integration + e2e) |
| Lint | ruff clean (30 source files) |
| Types | mypy clean |
| Python | 3.10+ (CI: 3.10, 3.12) |
| Version | 0.2.0 |
| License | MIT |
| CI | GitHub Actions (lint, type check, test on push/PR) |
| Docker | Dockerfile + docker-compose (GROBID) |

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
- No standard OCR format output (ALTO XML, hOCR) for digital library integration.
- Ground truth files exist (12 fixtures) but are derived from pipeline output — no human-curated references.

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
