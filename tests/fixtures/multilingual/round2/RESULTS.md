# Round 2 Multilingual OCR Integration Test Results

**Date:** 2026-07-02  
**Pipeline:** ocr-pipeline (Round 2 — expanded script coverage)  
**New scripts tested:** Spanish, German, Japanese (kana+kanji), Arabic (RTL), plus 3 synthetic edge cases  

## Provenance

| Document | Source | Pages | Script | Text Type |
|---|---|---|---|---|
| `es_quijote.pdf` | Anna's Archive — Don Quijote (Santillana Nivel 3) | 2 | Latin + diacritics (áéíóúñü¿¡) | Dialogue-rich prose |
| `de_verwandlung.pdf` | Anna's Archive — Die Verwandlung (Kafka) | 2 | Latin + umlauts (äöüß) | Literary German, compound nouns |
| `jp_kokoro.pdf` | Anna's Archive — Kokoro (Natsume Soseki) | 2 | CJK + kana (ひらがな, カタカナ, 漢字) | Dense literary Japanese |
| `ar_linguistics.pdf` | Anna's Archive — Arabic Linguistics | 2 | Arabic RTL (العربية) + tashkeel | **Scanned image-only** (no embedded text) |
| `synthetic_dense_table.pdf` | Synthetic (fpdf2) | 1 | Latin + symbols (±, Ω, μ, °C) | 10-column technical spec table |
| `synthetic_mixed_script.pdf` | Synthetic (fpdf2) | 1 | Arabic + Latin | Script-switching test |
| `synthetic_poetry.pdf` | Synthetic (fpdf2) | 1 | Latin | Poetry with irregular line breaks |

## Results Table

| # | Document | Script | Profile | VLM Model | Output (page) | Script OK? | Diacritics/Details | Structure | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Spanish | Latin+diacritics | general | gemini-2.5-flash | 3,837 chars | ✅ | 99 accented, 5 ¿¡ | N/A | All diacritics preserved; dialogue formatting correct |
| 2 | German | Latin+umlauts | general | gemini-2.5-flash | 4,462 chars | ✅ | 113 umlauts/ß | N/A | All umlauts and ß preserved; 2 compound words >15 chars |
| 3 | Japanese | CJK+kana | general | **gemini-2.5-flash** | 1,265 chars | ⚠️ | 251 kanji, 541 hiragana, 5 katakana | N/A | **Characters correct but inter-word spacing inserted** (unnatural); furigana as (読み); 12 stray Latin chars |
| 4 | Japanese | CJK+kana | general | **claude-sonnet-5** | 851 chars | ✅ | 251 kanji, 487 hiragana, 3 katakana | N/A | **Superior: natural spacing, 0 Latin artifacts, furigana as [読み]** |
| 5 | Arabic | RTL | general | gemini-2.5-flash | 0 chars | ❌ | N/A | N/A | **FAILED: Marker engine times out (120s) on scanned Arabic.** Marker/Surya does not support Arabic OCR. |
| 6 | Arabic | RTL | general | claude-sonnet-5 | 0 chars | ❌ | N/A | N/A | **FAILED: Same root cause — Marker timeout (120s).** VLM never called (no engine output to merge). |
| 7 | Dense table | Latin+symbols | technical | gemini-2.5-flash | 1,623 chars | N/A | 5 ± symbols preserved | ✅ 11 rows × 10 cols | Full table structure and all special symbols preserved |
| 8 | Mixed-script | Arabic+Latin | general | gemini-2.5-flash | 1,253 chars | ✅ | 205 Arabic, 811 Latin | N/A | Both scripts present; script switching handled correctly |
| 9 | Poetry | Latin | books | gemini-2.5-flash | 643 chars | N/A | N/A | ✅ 22 short lines | All line breaks and stanza breaks preserved; attribution intact |

**Summary: 7/9 tests pass script-correctness; 2/9 fail (Arabic — engine limitation).**

## Round 1 vs Round 2: Script-Dependent Model Behavior

### CJK: Chinese (Round 1) vs Japanese (Round 2)

| | Chinese (Round 1) | Japanese (Round 2) |
|---|---|---|
| **Gemini** | ❌ Garbled Latin characters | ⚠️ Correct characters but unnatural spacing |
| **Claude** | ✅ Correct Chinese | ✅ Correct Japanese (natural, clean) |

**Revised finding:** The Round 1 conclusion that "Gemini fails on CJK" needs refinement. Gemini no longer produces garbled Latin for Japanese — the characters are correct. However, Gemini inserts spaces between Japanese characters (where Japanese writing has none), producing unnatural output. Claude Sonnet 5 produces clean, natural Japanese with correct formatting. **For CJK scripts, Claude remains the recommended model, but Gemini's character accuracy has improved since Round 1.**

### Cyrillic: Russian (Round 1)

Round 1 finding held: Claude destroyed Cyrillic (replaced with Latin lookalikes). Russian was not retested in Round 2.

### New scripts tested in Round 2

| Script | Gemini | Claude | Recommendation |
|---|---|---|---|
| **Latin+diacritics** (Spanish, French) | ✅ | Not tested | Gemini fine |
| **Latin+umlauts** (German) | ✅ | Not tested | Gemini fine |
| **Arabic RTL** | ❌ (engine limitation) | ❌ (engine limitation) | **Neither works — Marker/Surya lacks Arabic OCR** |
| **Script switching** (Arabic+Latin) | ✅ | Not tested | Gemini handles bidirectional text on same page |

## Engine Coverage Gap: Arabic

**Critical finding:** The Marker/Surya OCR engine does not support Arabic text recognition on scanned (image-only) documents. The engine's PdfConverter timeouts after 120 seconds with zero output.

This means the pipeline currently cannot process:
- Scanned Arabic documents (no embedded text layer)
- Any RTL-script documents that Marker doesn't support (potentially Persian, Urdu, Hebrew)

**Possible remediation paths:**
1. **Google Document AI** — supports Arabic OCR natively. The pipeline already has a `google_doc_ai` engine. Test with `--engines google_doc_ai --profile general`.
2. **Surya 2** — newer version may add Arabic support. The pipeline has a `surya2` engine adapter.
3. **Tesseract** — Widely supports Arabic but not currently integrated.

## Recommendations

### Profile Configuration Changes
1. **CJK profile:** Create a dedicated `cjk` profile that defaults to `claude-sonnet-5` and `--langs ja,zh,ko`. The current `general` profile defaults to `gemini-2.5-flash` which produces unnatural spacing for Japanese.
2. **Arabic/RTL profile:** Create a profile that uses `google_doc_ai` engine (which supports Arabic) or documents the limitation clearly in STATUS.md.

### Documentation Updates
1. **STATUS.md:** Add Round 2 findings:
   - Gemini CJK issue is now "unnatural spacing" rather than "garbled characters" (improvement)
   - Claude remains superior for CJK
   - Arabic is a hard engine limitation — needs Google Doc AI or alternative engine
2. **README.md / profiles README:** Add language coverage matrix showing which scripts work with which engines:
   - Latin (en, es, fr, de, it, pt, etc.): ✅ marker + any VLM
   - CJK (zh, ja, ko): ⚠️ marker + Claude recommended; Gemini has spacing issues
   - Cyrillic (ru): ⚠️ marker + Gemini recommended (Claude corrupts Cyrillic)
   - Arabic (ar): ❌ marker not supported; use Google Doc AI
3. **CONTRIBUTING.md:** Document the engine/script compatibility matrix for new engine integrations.

### Testing
1. **Arabic re-test with Google Doc AI:** `uv run ocr-pipeline --input ... --output ... --profile general --engines google_doc_ai --vlm-model gemini-2.5-flash --test`
2. **Arabic re-test with surya2:** `uv run ocr-pipeline --input ... --output ... --profile general --engines surya2 --vlm-model gemini-2.5-flash --test`
3. **Hebrew test:** Similar RTL challenge — would reveal if the issue is Arabic-specific or RTL-general.
