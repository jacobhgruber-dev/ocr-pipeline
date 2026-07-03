# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ Supported |

## Reporting a Vulnerability

If you discover a security vulnerability in the OCR Pipeline, please report it
privately. Do NOT open a public issue.

Email: security@ocr-pipeline.dev (or open a private security advisory on GitHub)

We aim to respond within 48 hours and provide a fix within 7 days for
critical issues.

## Sensitive Data

This pipeline sends page images and OCR text to third-party APIs when VLM
merge is enabled:

- **Gemini** (Google): `gemini-2.5-flash` or other Gemini models
- **Claude** (Anthropic): `claude-sonnet-5`, `claude-haiku-4-5`, etc.
- **Mathpix**: for math-aware OCR engine
- **Google Document AI**: for enterprise OCR engine

If you are processing sensitive documents, use `--no-vlm` and
`--engines marker,tesseract` for fully local processing with no external API
calls. Review the privacy policies of Google, Anthropic, and Mathpix if using
their APIs.

## API Keys

Never commit `config.yaml` or `.env` files containing API keys to version
control. The project's `.gitignore` includes `.env` by default. Add your own
`config.yaml` to `.gitignore` as well:

```bash
echo "config.yaml" >> .gitignore
```

Prefer environment variables over config file keys when possible:
- `GEMINI_API_KEY` instead of `gemini_api_key` in config
- `ANTHROPIC_API_KEY` instead of `anthropic_api_key` in config
- `MATHPIX_APP_ID` / `MATHPIX_APP_KEY` instead of config values
