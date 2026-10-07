# AI harness — OpenCode MCP / agent guide

Machine-readable rules for agents (OpenCode, Grok Bot, Cloud Agents). Humans: [README](../README.md), [API-KEYS](API-KEYS.md).

## Default = research grade

**Default quality bar is highest research grade** (footnotes/endnotes, italics, headings, lists, citation/frontmatter metadata, page maps, QA gates). Do not silently degrade quality to save money.

Agents and MCP callers may **explicitly** opt into a hyper-cheap lower-quality run **per project** — never as an implied default.

### Explicit cheap override

| Mechanism | How |
|---|---|
| Profile | `profile_name="cheap"` (see `profiles/cheap.yaml`) |
| MCP / CLI | `vlm_enabled=false` (already default for merge) + `engines="marker"` or `"tesseract"` + small `--budget` |
| CLI | `--no-vlm --engines tesseract` or Marker-only on a slice |
| Config | `config.jstor.yaml` style text-layer path for JSTOR |

When using cheap mode, say so in logs/results (`quality_mode: cheap`). Research DB ingest still requires QA gates — cheap output usually stays PDF-archive only.

## Cost-aware routing (suggestions, not locks)

Profiles **suggest** engines/models; callers may always override. Do **not** hard-lock “model X is best.”

| Situation | Preferred path | Typical $/time |
|---|---|---|
| EPUB / DOCX / HTML / TeX | **Native extract only** (rich markdown) | ~$0; seconds |
| JSTOR / born-digital PDF with text layer | Marker `--disable_ocr` (or `jstor_fotc`) | ~$0 local; ~minutes/book |
| Clean scan, need structure | Marker / Docling (CPU) before VLM | low local CPU time |
| Dirty scan / handwriting / music OCR fail | Multi-engine + **selective** VLM | Gemini ~$0.001/page class; only failed pages |
| Hyper-cheap project override | `cheap` profile / tesseract-only | lowest; expect quality loss |

## Hard format rules

1. **EPUB** = stylized HTML in a zip → **never** Marker/OCR by default. Use `EpubSource` HTML→markdown (headings, italics, bold, lists) + OPF metadata. Override only if the EPUB is image-only pages (rare; document why).
2. **DOCX** → native run-level markdown (italics/bold/headings/lists) + metadata; not OCR unless render-only fallback is required.
3. **Images / TIFF** → ImageSource OCR path; expect rotation/preprocess; VLM only if quality needs it.

## Success criteria

1. Research-grade default; cheap only when explicitly requested.
2. Format-native extract for EPUB/DOCX/HTML/TeX with **structure preserved** (not thin plain text).
3. Marker text-layer when `pdffonts` shows real fonts.
4. Never invent missing OpenCode `{file:…}` secret paths.
5. Wipe page PNGs after runs.
6. No `qa_status: pass` without gates.

## MCP tools (do not invent others)

`ocr_detect`, `ocr_formats`, `ocr_profiles`, `ocr_document`, `ocr_pdf`, `ocr_page`, `ocr_handwriting`, `ocr_status`, `ocr_languages`.

### Profiles

Built-in: `general`, `academic`, `mathematical`, `legal`, `technical`, `books`, `grok-value`, `grok-quality`.  
User YAML: `jstor_fotc`, `doml54`, `latin_martyrology`, `spanish_devotional`, **`cheap`** (explicit low-quality override).  
**Planned:** `handbook_pe` (empty until PE sample).

`ocr_profiles` suggestions are **defaults you may override** — not dogma.

## Env (OpenCode)

Working set **only** (files must exist):

- `MATHPIX_APP_ID` / `MATHPIX_APP_KEY` → `{file:~/.secrets/mathpix-app-id|key}`
- `GEMINI_API_KEY` → `{file:~/.secrets/gemini-api-key}`
- `OCR_PIPELINE_MARKER_VENV` → absolute `.marker-venv`

**Do not add** `ANTHROPIC_API_KEY={file:~/.secrets/anthropic-api-key}` unless that file exists. See [API-KEYS.md](API-KEYS.md).

## Bake-off layout

```text
Academic Research/data/jstor_md/bakeoff/samples/   # binaries + sha256
ocr-pipeline/bakeoff/{samples,work,results,scripts}/
```

## What NOT to invent

- Fake profiles as shipped (`handbook_pe` until merged).
- Whole-book VLM on clean JSTOR text layers.
- Missing secret `{file:}` refs.
- Thin EPUB/DOCX dumps that drop italics/headings when rich native exists.
- Claiming gold without QA gates.

## Config files

| File | Role |
|---|---|
| `config.yaml` | Local default (gitignored) |
| `config.jstor.yaml` | JSTOR text-layer (VLM off) |
| `config.hagiography.yaml` | Image-heavy; VLM on — not MCP default |
| `profiles/cheap.yaml` | Explicit cheap override |
