# OCR bake-off harness

Evidence-based profile validation. Plan: workspace `ocr-pipeline-major-audit-plan.md`.

## Layout

| Path | Contents |
|---|---|
| `samples/` | Symlinks to `Academic Research/data/jstor_md/bakeoff/samples/` (**gitignored**) |
| `scripts/` | `smoke_pdftotext.py`, `marker_slice.sh`, `format_native_smoke.sh`, `score_skeleton.py` |
| `results/` | JSONL/CSV metrics + `corpus_manifest.json` |
| `work/` | Intermediates (**gitignored**; wipe images after runs) |

## P0 first-pass (cheap)

```bash
python3 bakeoff/scripts/smoke_pdftotext.py
# Marker 5-page slices (text-layer):
bash bakeoff/scripts/marker_slice.sh
# EPUB/DOCX native (no OCR) — see format_native results
python3 bakeoff/scripts/score_skeleton.py
```

No full-book VLM in P0. PE handbook deferred (`handbook_pe` empty until sample).

## Secrets

See [`docs/API-KEYS.md`](../docs/API-KEYS.md). OpenCode MCP uses Mathpix + Gemini + Marker venv only unless `~/.secrets/anthropic-api-key` already exists.
