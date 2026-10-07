# OCR Pipeline config applied — 2026-10-07

Research-backed refresh (audit → implement → GitHub). No mass engine rewrite.

## GitHub

- https://github.com/jacobhgruber-dev/ocr-pipeline
- `main` (unprotected) — commit+push
- Version **0.3.1**

## What changed

1. OpenCode MCP: `OCR_PIPELINE_MARKER_VENV` + `ANTHROPIC_API_KEY={file:~/.secrets/anthropic-api-key}`
2. `vlm_enabled` default **False**
3. Models: `gemini-3.8-flash` / `claude-sonnet-5-5`
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
    "ANTHROPIC_API_KEY": "{file:~/.secrets/anthropic-api-key}",
    "OCR_PIPELINE_MARKER_VENV": "/Users/jacobgruber/Projects/ocr-pipeline/.marker-venv"
  }
}
```

## Manual

```bash
chmod 600 ~/.secrets/anthropic-api-key  # after creating one-line key file
# Restart OpenCode
```

## Intentionally NOT changed

- Engine implementations / selective-repair P1
- Historical comparison docs
- Mass dep upgrade / Marker into main uv env
- gitignored `config.yaml` / secrets
