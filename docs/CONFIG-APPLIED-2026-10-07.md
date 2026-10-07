# OCR Pipeline config applied — 2026-10-07

Research-backed refresh (audit → implement → GitHub). No mass engine rewrite.

## GitHub

- https://github.com/jacobhgruber-dev/ocr-pipeline
- `main` (unprotected) — commit+push
- Version **0.3.1** — commit [`a5a552e`](https://github.com/jacobhgruber-dev/ocr-pipeline/commit/a5a552e0bf5e1fb53bd169d8c15b39c0babc39b1)

## What changed

1. OpenCode MCP: `OCR_PIPELINE_MARKER_VENV` + Mathpix + Gemini file refs only (**do not** add `ANTHROPIC_API_KEY={file:~/.secrets/anthropic-api-key}` — that path does not exist and breaks desktop OpenCode with ConfigInvalidError). Anthropic stays on existing auth if/when used.
2. `vlm_enabled` default **False**
3. Models: `gemini-3.8-flash` / `claude-sonnet-5-5` (Claude only when Anthropic auth is already available)
4. Config split: hagiography / jstor / default
5. `jstor_fotc` + `docs/JSTOR-ROUTING.md`
6. Project-root profiles load

## Paste-ready OpenCode fragment (already applied)

```json
"ocr-pipeline": {
  "type": "local",
  "command": ["uv", "run", "--directory", "/Users/jacobgruber/Projects/ocr-pipeline", "ocr-pipeline-mcp"],
  "enabled": true,
  "environment": {
    "MATHPIX_APP_ID": "{file:~/.secrets/mathpix-app-id}",
    "MATHPIX_APP_KEY": "{file:~/.secrets/mathpix-app-key}",
    "GEMINI_API_KEY": "{file:~/.secrets/gemini-api-key}",
    "OCR_PIPELINE_MARKER_VENV": "/Users/jacobgruber/Projects/ocr-pipeline/.marker-venv"
  }
}
```

## Manual

Restart OpenCode after MCP env changes. Do **not** invent `~/.secrets/anthropic-api-key` for OpenCode — missing `{file:…}` refs invalidate the whole config.

## Intentionally NOT changed

- Engine implementations / selective-repair P1
- Historical comparison docs
- Mass dep upgrade / Marker into main uv env
- gitignored `config.yaml` / secrets
