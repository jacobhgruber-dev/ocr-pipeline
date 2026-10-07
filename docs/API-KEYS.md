# API keys & secrets

How credentials work for CLI, library, and **OpenCode MCP**. Follow this exactly — a missing `{file:…}` path **invalidates the whole OpenCode config** (`ConfigInvalidError`).

## Required vs optional

| Secret | Required? | Used for | Get it |
|---|---|---|---|
| **Gemini** `GEMINI_API_KEY` | **Recommended** (default VLM when VLM is on) | VLM merge / selective page repair | [Google AI Studio](https://aistudio.google.com/apikey) |
| **Mathpix** `MATHPIX_APP_ID` + `MATHPIX_APP_KEY` | Optional | Math/equation engine; STEM & handbook profiles | [Mathpix console](https://mathpix.com) |
| **Anthropic** `ANTHROPIC_API_KEY` | Optional | Claude VLM fallback (diacritics / citations) | Anthropic console — **only if you already use Claude auth** |
| **xAI** `XAI_API_KEY` | Optional | Grok VLM for CJK/math profiles | xAI console |
| Marker venv | Local path, not a key | `OCR_PIPELINE_MARKER_VENV` → `.marker-venv` | Created by install script |

**Born-digital JSTOR / text-layer PDFs** often need **no VLM key at all** — Marker `--disable_ocr` (or profile `jstor_fotc` with `vlm_enabled: false`) is enough.

## Where to put keys (Mac)

Prefer one-line secret files (no trailing commentary):

```text
~/.secrets/gemini-api-key          # single line
~/.secrets/mathpix-app-id
~/.secrets/mathpix-app-key
# OPTIONAL — create ONLY if the file will exist:
# ~/.secrets/anthropic-api-key
```

```bash
chmod 600 ~/.secrets/gemini-api-key ~/.secrets/mathpix-app-id ~/.secrets/mathpix-app-key
```

Or export env vars in the shell / launchd (same names as the table).

## OpenCode MCP env (working set)

**Only reference `{file:…}` paths that already exist.** On this machine the working `ocr-pipeline` MCP block is:

```json
"ocr-pipeline": {
  "type": "local",
  "command": [
    "uv", "run", "--directory",
    "/Users/jacobgruber/Projects/ocr-pipeline",
    "ocr-pipeline-mcp"
  ],
  "enabled": true,
  "environment": {
    "MATHPIX_APP_ID": "{file:~/.secrets/mathpix-app-id}",
    "MATHPIX_APP_KEY": "{file:~/.secrets/mathpix-app-key}",
    "GEMINI_API_KEY": "{file:~/.secrets/gemini-api-key}",
    "OCR_PIPELINE_MARKER_VENV": "/Users/jacobgruber/Projects/ocr-pipeline/.marker-venv"
  }
}
```

### Never do this

- ❌ `"ANTHROPIC_API_KEY": "{file:~/.secrets/anthropic-api-key}"` when that file **does not exist** — breaks desktop OpenCode.
- ❌ Inventing placeholder secret files just to satisfy a `{file:}` ref.
- ❌ Committing real keys into `config.yaml` or the repo.

If you later create `~/.secrets/anthropic-api-key` (mode `600`), *then* you may add the `{file:}` line. Until then, leave Anthropic out of MCP env; Claude stays on whatever auth you already use outside this file ref.

## CLI / library

```bash
export GEMINI_API_KEY="$(cat ~/.secrets/gemini-api-key)"
# optional:
export MATHPIX_APP_ID="$(cat ~/.secrets/mathpix-app-id)"
export MATHPIX_APP_KEY="$(cat ~/.secrets/mathpix-app-key)"
# export ANTHROPIC_API_KEY="…"   # only if you have a key
```

`config.yaml` may set the same fields; env wins. See `config.example.yaml`.
