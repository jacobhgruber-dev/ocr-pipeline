# JSTOR / FOTC routing (2026-10-07)

How to convert JSTOR merged scholarly PDFs without burning VLM budget or
leaving OCR garbage behind.

## Default (good text layer — most JSTOR books)

1. Smoke the PDF: `pdffonts` / short `pdftotext` — real fonts + sane extract?
2. **Marker text-layer path** (preferred for FOTC pilots):
   ```bash
   # From ocr-pipeline/.marker-venv or Marker CLI:
   marker_single BOOK.pdf --output_dir OUT --disable_ocr --paginate_output
   ```
3. Or pipeline CLI with JSTOR config (VLM off):
   ```bash
   cd /Users/jacobgruber/Projects/ocr-pipeline
   uv run ocr-pipeline --config config.jstor.yaml -i /path/to/book.pdf -o /path/to/out
   ```
4. **Postprocess** (reflow, ordered footnotes, page map) → **QA gates**
   (`placeholder_count`, glyph garbage rate, italics/footnote spot-check).
5. Keep only: final `.md`, page_map JSON, thin QA log, sha256.
   Delete renders / staging images after QA.

## OpenCode MCP (agents)

```
ocr_document(
  file_path="…/FOTC….pdf",
  output_dir="…/Academic Research/data/jstor_md/…",
  engines="marker",
  vlm_enabled=false,          # REQUIRED for JSTOR text-layer
  profile_name="jstor_fotc",
  languages="en,la,el",
  test_mode=true              # 3-page smoke before full book
)
```

MCP tool default is still `vlm_enabled=true` (legacy). **Always pass false**
for JSTOR until selective page repair exists. Project `config.yaml` now
defaults VLM off so CLI/MCP bare loads are safe; tool args still win.

## Full pipeline (image-only / bad text layer)

```
ocr_document(…, engines="marker,mathpix", vlm_enabled=true,
             vlm_model="gemini-3.8-flash", profile_name="academic")
```

Citation-critical repair pages: `vlm_model="claude-sonnet-5-5"` (needs
`ANTHROPIC_API_KEY` via `~/.secrets/anthropic-api-key`).

## Selective repair (after QA fail)

Do **not** re-run whole-book VLM. Re-process only flagged pages
(`ocr_page` / Marker `--force_ocr` page ranges / VLM academic on fails).

## Config map

| File | Role |
|------|------|
| `config.yaml` | Default MCP/CLI — VLM **off**, general |
| `config.jstor.yaml` | JSTOR paths + `jstor_fotc` profile |
| `config.hagiography.yaml` | Latin hagiography — always-VLM (`agreement_threshold: 1.0`) |
| `config.example.yaml` | Annotated template |
| `profiles/jstor_fotc.yaml` | FOTC / JSTOR scholarly prompt |

Hagiography CLI: `uv run ocr-pipeline --config config.hagiography.yaml …`
