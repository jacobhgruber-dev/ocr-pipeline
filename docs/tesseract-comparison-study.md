# Tesseract Comparison Study — Methodology

**Purpose:** Determine whether Tesseract should be adopted as a companion (or alternative) to Marker in the OCR pipeline, and under what conditions.

**Date:** 2026-07-02
**Status:** Design phase — ready for execution

---

## 1. Research Questions

| # | Question | Answer Format |
|---|---|---|
| Q1 | Does Tesseract produce better or worse raw text than Marker? | Per-script CER/WER comparison table |
| Q2 | Does adding Tesseract to the engine mix improve final VLM-merged output? | Cross-CER between `marker+VLM` and `marker+tesseract+VLM` |
| Q3 | For which scripts/profiles should Tesseract be recommended? | Engine recommendation matrix (suggested / optional / not recommended) |
| Q4 | Is Tesseract worth the cost? (free, but costs time) | Median time-per-page comparison; cost delta analysis |
| Q5 | Should Tesseract be a default fallback when Marker fails? | Boolean + failure-recovery rate across 11 PDFs |

---

## 2. Pre-Flight: Known Issue — Tesseract Language Code Mismatch

**Bug:** The pipeline passes ISO 639-1 (2-letter) codes to Tesseract (`config.languages`), but
pyTesseract's `lang` parameter requires **ISO 639-2/T (3-letter)** codes (e.g., `rus`, not `ru`).

This means Tesseract silently falls back to English for all non-English languages unless a
workaround is applied. Running the comparison without fixing this produces false negatives
for every non-English script.

**Required fix for the study** — apply this mapping before each run:

| Config code (ISO 639-1) | Tesseract code (ISO 639-2/T) |
|---|---|
| `en` | `eng` (default anyway) |
| `es` | `spa` |
| `de` | `deu` |
| `ru` | `rus` |
| `zh` | `chi_sim` (simplified; use `chi_tra` for traditional) |
| `ar` | `ara` |
| `fr` | `fra` |
| `el` | `ell` |

**Implementation note:** `TesseractEngine.recognize()` receives a `languages: list[str]` parameter.
The fix can be applied in one of two ways:
1. Patch `_run_engines_parallel()` in `pipeline.py` to translate codes before passing to Tesseract
   (proper but invasive)
2. Monkey-patch a `LANG_MAP` dict in `tesseract.py` (quickest for the study)

Use option 2 for the study; open a bug report for option 1 to be implemented permanently.

---

## 3. Test PDFs — Prioritized Selection (11 of 24+)

Selection criteria: cover all 6 core profiles, 8 distinct scripts, and as many edge cases
as possible within a manageable batch size.

### Core English (6 PDFs across 5 profiles)

| # | Fixture Path | Profile | Pages | Why Selected |
|---|---|---|---|---|
| 1 | `tests/fixtures/academic/citations_body.pdf` | academic | 1 | Dense parenthetical citations, body text |
| 2 | `tests/fixtures/academic/title_abstract.pdf` | academic | 1 | Author list with superscripts, abstract |
| 3 | `tests/fixtures/books/block_quotes.pdf` | books | 1 | Block quotes, em-dash attributions |
| 4 | `tests/fixtures/books/chapter_opening.pdf` | books | 1 | Chapter heading, narrative prose |
| 5 | `tests/fixtures/legal/court_opinion.pdf` | legal | 1 | Party names, docket numbers, legal formatting |
| 6 | `tests/fixtures/technical/datasheet_specs.pdf` | technical | 1 | Tables with tolerance values, callout boxes |

### Non-English (4 PDFs across 4 scripts)

| # | Fixture Path | Profile | Pages | Script | Why Selected |
|---|---|---|---|---|---|
| 7 | `tests/fixtures/multilingual/round2/inputs/es_quijote/es_quijote.pdf` | books | 2 | Latin + diacritics | Accented characters (áéíóúñü¿¡) |
| 8 | `tests/fixtures/multilingual/round2/inputs/de_verwandlung/de_verwandlung.pdf` | books | 2 | Latin + umlauts | Umlauts, ß, long compounds |
| 9 | `tests/fixtures/multilingual/russian_math.pdf` | mathematical | 2 | Cyrillic | Tesseract Cyrillic support test; Claude vs Gemini Cyrillic bug |
| 10 | `tests/fixtures/multilingual/chinese_ml.pdf` | general | 2 | CJK | Tesseract CJK support; Gemini spacing issue |

### Edge Case (1 PDF)

| # | Fixture Path | Profile | Pages | Script | Why Selected |
|---|---|---|---|---|---|
| 11 | `tests/fixtures/multilingual/round2/inputs/ar_linguistics/ar_linguistics.pdf` | general | 2 | Arabic (RTL) | **Critical:** Marker fails entirely — this is the strongest test of Tesseract-as-fallback |

**Total: 11 PDFs, 16 pages** (English: 6 pages; non-English: 10 pages)

### Excluded PDFs (with rationale)

| PDF | Why Excluded |
|---|---|
| `mathematical/lemma_proof.pdf` | Similar characteristics to theorem_proof; omit to keep batch size manageable |
| `general/periodic_table.pdf` | Complex grid layout — less representative of pipeline's typical workload |
| `general/mixed_format.pdf` | Overlaps with technical profile characteristics |
| `legal/section_hierarchy.pdf` | Heavily redundant with court_opinion (same document, different page) |
| `technical/pin_config.pdf` | Same document source as datasheet_specs |
| `multilingual/french_les_mis.pdf` | Latin script already covered by Spanish (diacritics) and German (special chars) |
| `multilingual/greek_ethics.pdf` | Greek support is lower priority than Cyrillic and CJK |
| `multilingual/topology_math.pdf` | English math — mathematical profile already covered |
| `round2/*/jp_kokoro.pdf` | Japanese: Tesseract supports it but Gemini has known spacing issues; lower priority than Chinese |
| `round2/synthetic_*.pdf` | Synthetic — less representative of real-world documents |

---

## 4. Test Matrix

### Engine × VLM Configurations

| Config ID | Engines | VLM Model | Purpose |
|---|---|---|---|
| **M-G** | `marker` | `gemini-2.5-flash` | **Baseline** (already exists for English; re-run for non-English if different model was used) |
| **T-N** | `tesseract` | `--no-vlm` | Raw Tesseract quality (debug only — skip for final comparison) |
| **T-G** | `tesseract` | `gemini-2.5-flash` | Tesseract-only with VLM — "can Tesseract replace Marker?" |
| **MT-G** | `marker,tesseract` | `gemini-2.5-flash` | Both engines → VLM — "does adding Tesseract help?" |

### Per-PDF Run Schedule

| PDF # | Script | M-G (baseline) | T-G | MT-G | Notes |
|---|---|---|---|---|---|
| 1-6 | English | USE EXISTING | YES | YES | Baseline from `tests/fixtures/{profile}/output/` |
| 7 | Spanish | CHECK EXISTING | YES | YES | Round 2 output uses `gemini-2.5-flash` — use if same engine was marker |
| 8 | German | CHECK EXISTING | YES | YES | Same as above |
| 9 | Russian | CHECK EXISTING | YES | YES | Use `output_russian_best/` if it exists with gemini |
| 10 | Chinese | CHECK EXISTING | YES | YES | Use `output_chinese_cheap/` (gemini-2.0-flash?) or re-run |
| 11 | Arabic | RE-RUN marker | YES | YES | ALL existing Arabic outputs are empty (Marker timeout) |

**Re-run marker-only baseline** for: Chinese (#10) and Arabic (#11) if gemini-2.5-flash baseline is absent.

### CLI Command Templates

```bash
# Tesseract-only, with VLM
uv run ocr-pipeline \
  --input tests/fixtures/{profile}/ \
  --output tests/fixtures/{profile}/output_tesseract/ \
  --engines tesseract \
  --vlm-model gemini-2.5-flash \
  --profile {profile} \
  --langs {lang_code}

# Marker+Tesseract, with VLM
uv run ocr-pipeline \
  --input tests/fixtures/{profile}/ \
  --output tests/fixtures/{profile}/output_marker_tesseract/ \
  --engines marker,tesseract \
  --vlm-model gemini-2.5-flash \
  --profile {profile} \
  --langs {lang_code}

# Tesseract-only, no VLM (debug only)
uv run ocr-pipeline \
  --input tests/fixtures/{profile}/ \
  --output tests/fixtures/{profile}/output_tesseract_novlm/ \
  --engines tesseract \
  --no-vlm \
  --profile {profile} \
  --langs {lang_code}
```

**Full run plan (primary runs only — T-G and MT-G for each PDF):**

For single-file PDFs (academic, books, legal, technical), run the file directly:

```bash
# Example: academic/citations_body.pdf
uv run ocr-pipeline \
  --input tests/fixtures/academic/ \
  --output tests/fixtures/academic/output_tesseract/ \
  --engines tesseract \
  --vlm-model gemini-2.5-flash \
  --profile academic --langs en
```

For multi-file profile directories, run the entire directory — the pipeline processes all PDFs it finds:

```bash
# Example: Spanish + German (both in round2 directory)
# Copy target PDFs to a temp directory or run each individually
uv run ocr-pipeline \
  --input tests/fixtures/multilingual/round2/inputs/es_quijote/ \
  --output tests/fixtures/multilingual/round2/outputs_es_tesseract/ \
  --engines tesseract \
  --vlm-model gemini-2.5-flash \
  --profile books --langs es
```

---

## 5. Metrics Collection

### Per-Page Metrics (extracted from output files)

| Metric | Source | Data Type | Collection Method |
|---|---|---|---|
| `char_count` | `page_NNNN_final.md` | int | `len(md_text)` |
| `word_count` | `page_NNNN_final.md` | int | `len(md_text.split())` |
| `non_latin_ratio` | `page_NNNN_final.md` | float (0-1) | Ratio of non-Latin characters to total |
| `script_preservation` | `page_NNNN_final.md` | bool/qualitative | Manual check: are expected scripts present? |
| `vlm_model_used` | `page_NNNN_raw.json` | str | From `vlm_model` field |
| `engines_agreement` | `page_NNNN_raw.json` | float (0-1) | From `engines_agreement` field — available only for multi-engine runs |
| `duration_sec` | pipeline log or `EngineOutput.duration_sec` | float | OCR time per engine (not VLM time) |
| `cost_usd` | pipeline stats / `page_NNNN_raw.json` | float | From pipeline stats or VLM cost tracking |
| `has_error` | `page_NNNN_raw.json` | bool | Check `error` fields in engine_outputs |
| `empty_output` | `page_NNNN_final.md` | bool | File exists but has zero meaningful content |

### Cross-Run Comparison Metrics

| Metric | Description | Calculation |
|---|---|---|
| **Cross-CER** | Character Error Rate between two outputs | `editdistance.eval(marker_output, tesseract_output) / max(len(a), len(b))` |
| **Word count delta** | Relative word count difference | `abs(wc_a - wc_b) / max(wc_a, wc_b, 1)` |
| **Δchar_count** | Character count change | `char_count_tesseract - char_count_marker` |

### Per-Engine Raw Metrics (from no-VLM runs only)

| Metric | Source | Data Type |
|---|---|---|
| `engine_text` | Intermediate engine output (must capture) | str |
| `engine_duration` | `EngineOutput.duration_sec` | float |
| `engine_confidence` | `EngineOutput.confidence` (if available) | float \| None |

---

## 6. Aggregation & Analysis

### 6.1 Per-Script Summary Table

For each script category, produce a row:

| Script | PDFs | Marker+VLM chars | Tesseract+VLM chars | MT+VLM chars | Cross-CER (M-G vs T-G) | Cross-CER (M-G vs MT-G) | Winner |
|---|---|---|---|---|---|---|---|
| Latin (English) | #1-6 | ... | ... | ... | ... | ... | M/T/MT |
| Latin+diacritics | #7 | ... | ... | ... | ... | ... | M/T/MT |
| Latin+umlauts | #8 | ... | ... | ... | ... | ... | M/T/MT |
| Cyrillic | #9 | ... | ... | ... | ... | ... | M/T/MT |
| CJK | #10 | ... | ... | ... | ... | ... | M/T/MT |
| Arabic | #11 | 0 (fail) | ... | ... | N/A | ... | T (by default) |

### 6.2 Decision Matrix

Produce a recommendation table:

| Profile/Script | Suggested Engine | Optional Engine | Not Recommended | Notes |
|---|---|---|---|---|
| academic (en) | marker | tesseract | — | Tesseract quality comparison |
| books (en) | marker | tesseract | — | ... |
| legal (en) | marker | tesseract | — | ... |
| technical (en) | marker | tesseract | — | Tables are key |
| mathematical (en) | marker | tesseract | — | LaTeX preservation |
| Latin+diacritics (es,fr) | marker | tesseract | — | Diacritic accuracy |
| Latin+umlauts (de) | marker | tesseract | — | Umlaut/ß accuracy |
| Cyrillic (ru) | TBD from results | TBD | TBD | Claude Cyrillic bug makes this interesting |
| CJK (zh,ja,ko) | TBD from results | TBD | TBD | Gemini spacing issue; Tesseract CJK support |
| Arabic (ar) | tesseract | — | marker | Marker fails entirely on scanned Arabic |

### 6.3 Cost-Benefit Analysis

| Metric | Marker-only | Tesseract-only | Marker+Tesseract |
|---|---|---|---|
| Median time-per-page (s) | ... | ... | ... |
| Estimated cost-per-page (USD) | $0.00 (engine) + gemini | $0.00 (engine) + gemini | $0.00 (engines) + gemini |
| Failure rate (%) | ... | ... | ... |
| Avg char count | ... | ... | ... |
| Avg Cross-CER vs baseline | 0.00 (baseline) | ... | ... |

### 6.4 Q5: Tesseract-as-Fallback Analysis

| PDF | Marker succeeded? | Tesseract succeeded? | Combined succeeded? | Tesseract saved it? |
|---|---|---|---|---|
| #11 Arabic | NO (timeout) | TBD | TBD | TBD |

If Tesseract produces any output for Arabic (where Marker times out), the answer to Q5 is immediately YES — Tesseract should be a default fallback when Marker fails (at minimum for RTL scripts).

---

## 7. Execution Plan

### Prerequisites

1. **Fix Tesseract language code mapping** (see §2) — apply ISO 639-1 → 639-3 mapping in `tesseract.py` or via monkey-patch
2. **Verify tesseract binary** is on PATH: `tesseract --version`
3. **Verify language packs** are installed:
   ```bash
   tesseract --list-langs
   # Expected: eng, spa, deu, rus, chi_sim, ara (at minimum)
   ```
4. **Clear checkpoints** between runs to avoid stale data:
   ```bash
   rm -rf tests/fixtures/*/output_tesseract/
   rm -rf tests/fixtures/*/output_marker_tesseract/
   ```

### Run Order

1. **Batch 1: English PDFs** (#1-6) — fastest, establishes baseline quality comparison
   - Prerequisites: tesseract with `eng` language pack
   - Run T-G and MT-G for academic/, books/, legal/, technical/ sequentially
   
2. **Batch 2: Latin-extended PDFs** (#7-8) — Spanish, German
   - Prerequisites: `spa`, `deu` language packs
   
3. **Batch 3: Cyrillic + CJK** (#9-10) — Russian, Chinese
   - Prerequisites: `rus`, `chi_sim` language packs
   
4. **Batch 4: Arabic** (#11) — highest-interest edge case
   - Prerequisites: `ara` language pack

### Data Capture

After each run, collect:
1. Copy each `page_NNNN_final.md` to a comparison directory
2. Copy each `page_NNNN_raw.json` for metadata
3. Capture pipeline stdout/stderr for duration and cost data
4. Record wall-clock time: `time uv run ocr-pipeline ...`

---

## 8. Script for Automated Metrics Extraction

After all runs complete, run an extraction script (to be built) that:

1. For each PDF × config combination:
   - Load `page_NNNN_final.md` → compute `char_count`, `word_count`, `non_latin_ratio`
   - Load `page_NNNN_raw.json` → extract `vlm_model`, `engines_agreement`, engine outputs
2. For each PDF across configs:
   - Compute Cross-CER using `editdistance` (or `python-Levenshtein`)
   - Compute word count deltas
3. Output a CSV or JSON results file with one row per (PDF, config) combination

**Output schema:**
```csv
pdf_name,profile,script,engine_config,vlm_config,char_count,word_count,non_latin_ratio,cost_usd,duration_sec,engine_success,cross_cer_vs_marker,word_delta_vs_marker
```

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Tesseract lang pack missing | Medium | Blocks non-English tests | Run `tesseract --list-langs` before starting; install missing packs |
| Marker timeout on Arabic (re-run) | High | Wastes time | Skip re-running marker-only Arabic if all existing outputs are empty — use the known result |
| Checkpoint interference | Medium | Stale results | Delete checkpoints between config runs, or use separate output dirs |
| Gemini rate limiting | Low | Slowdown | Budget ~$0.50 for all VLM calls; use retry config |
| Tesseract produces garbage for CJK | Medium | False negative | Verify `chi_sim` traineddata; try both `chi_sim` and `chi_tra` |
| Different VLM model in existing baselines | Low | Confounding factor | Verify existing output's `vlm_model` field; re-run marker-only if model differs |

---

## 10. Timeline Estimate

| Phase | PDFs | Estimated Time |
|---|---|---|
| Prerequisites (fix lang mapping, install packs) | — | 30 min |
| Batch 1: English (6 PDFs × 2 configs = 12 runs) | #1-6 | ~15 min |
| Batch 2: Latin-extended (2 PDFs × 2 configs = 4 runs) | #7-8 | ~10 min |
| Batch 3: Cyrillic + CJK (2 PDFs × 2 configs = 4 runs) | #9-10 | ~10 min |
| Batch 4: Arabic (1 PDF × 2 configs = 2 runs) | #11 | ~5 min |
| Metrics extraction & analysis | — | 30 min |
| Report writing | — | 60 min |
| **Total** | | **~2.5 hours** |
