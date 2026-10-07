# AI harness — OpenCode MCP / agent guide

Machine-readable rules for agents (OpenCode, Grok Bot, Cloud Agents). Humans: start with [README](../README.md) and [API-KEYS](API-KEYS.md).

## Success criteria

1. Prefer **format-native extract** (EPUB/DOCX/HTML/TeX) over OCR.
2. Prefer **Marker text-layer** (`--disable_ocr`) when `pdffonts` shows real fonts and `pdftotext` yields substantial text.
3. Use **full multi-engine + VLM** only for image-only / dirty scans / QA-failed pages.
4. Never invent missing secret `{file:…}` paths in OpenCode config.
5. Wipe page PNGs / staging images after runs; keep MD + thin metrics only.
6. Do not mark research-DB `qa_status: pass` without footnote/italics/reflow/page-map gates.

## MCP tools (do not invent others)

| Tool | Use |
|---|---|
| `ocr_detect` | Preview format / text-extractability before spending |
| `ocr_formats` | Claimed extensions |
| `ocr_profiles` | Built-in + user YAML profiles |
| `ocr_document` / `ocr_pdf` | Batch/file convert |
| `ocr_page` | Single-page / selective repair |
| `ocr_handwriting` | Handwriting path |
| `ocr_status` | Engines / config health |
| `ocr_languages` | Language packs |

## Profile selection (do not freestyle names)

Built-in: `general`, `academic`, `mathematical`, `legal`, `technical`, `books`, `grok-value`, `grok-quality`.  
User YAML (repo `profiles/`): `jstor_fotc`, `doml54`, `latin_martyrology`, `spanish_devotional`.  
**Planned (empty until bake-off):** `handbook_pe` — PE/electrical handbooks (tables, equations, callouts, procedures). Do not claim it exists until shipped.

Routing cheat-sheet:

| Input | First action | Profile / flags |
|---|---|---|
| JSTOR merged scholarly PDF, good text layer | Marker `--disable_ocr` | `jstor_fotc`, `vlm_enabled=false` |
| Footnote-heavy academic scan | Multi-engine + selective VLM | `academic` |
| STEM / equations | Marker + Mathpix if keyed | `mathematical` / `technical` |
| Image TIFF/PNG of text | ImageSource → OCR engines; VLM if quality needs it | `general` or domain profile |
| EPUB / DOCX | Native extract (pandoc / pipeline source) — **no OCR** | n/a |
| PE handbook | Deferred — collect sample, then `handbook_pe` | TBD |

## Env (OpenCode)

Working set **only**:

- `MATHPIX_APP_ID` / `MATHPIX_APP_KEY` → `{file:~/.secrets/mathpix-app-id|key}` (files **exist**)
- `GEMINI_API_KEY` → `{file:~/.secrets/gemini-api-key}` (exists)
- `OCR_PIPELINE_MARKER_VENV` → absolute `.marker-venv` path

**Do not add** `ANTHROPIC_API_KEY={file:~/.secrets/anthropic-api-key}` unless that file is present. See [API-KEYS.md](API-KEYS.md).

## Bake-off corpus layout (P0+)

```text
Academic Research/data/jstor_md/bakeoff/samples/   # binaries + .sha256 (canonical)
ocr-pipeline/bakeoff/
  samples/     # symlinks → AR (gitignored)
  work/        # intermediates (gitignored; wipe images)
  results/     # JSONL/CSV metrics (commit schemas + non-secret rows)
  scripts/     # smoke_pdftotext.py, marker_slice.sh, …
```

Agents: stage small files only; no mass Drive harvest; stay off shared box browser when Online Task Worker is harvesting.

## What NOT to invent

- Fake profiles (`handbook_pe` until merged), fake engines, or “gold” QA without gates.
- Whole-book VLM on clean JSTOR text layers.
- OpenCode `{file:}` refs for absent secrets.
- Leaving `renders/*.png` or Marker image dumps behind.
- Speaking for the user / sending external messages without approval.

## Config files

| File | Role |
|---|---|
| `config.yaml` | Local default (gitignored) |
| `config.jstor.yaml` | JSTOR / FOTC text-layer (VLM off) |
| `config.hagiography.yaml` | Image-heavy Latin; VLM on — **not** MCP default |
| `config.example.yaml` | Template |

## Related docs

- [JSTOR-ROUTING.md](JSTOR-ROUTING.md)
- [API-KEYS.md](API-KEYS.md)
- Bake-off plan: workspace handoff `ocr-pipeline-major-audit-plan.md`
