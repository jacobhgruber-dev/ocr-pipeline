# OCR Pipeline

**Multi-engine OCR with VLM merge for PDF documents.**

Three OCR engines run in parallel on each page. A Vision Language Model (Gemini or Claude) reads the page image and all engine outputs, then writes a single clean markdown transcription — correcting errors, resolving disagreements, and preserving document structure.

Built-in checkpoint/resume means you can stop and restart without losing progress. Budget tracking prevents surprise API bills. Every API call gets exponential-backoff retry. The pipeline is both a CLI tool and a Python library.

---

## Quickstart

```bash
# 1. Clone the package
git clone https://github.com/jacobhgruber-dev/academic-research-mcp.git
cd academic-research-mcp/ocr_pipeline

# 2. Install
uv sync

# 3. Configure
cp config.example.yaml config.yaml
# Edit config.yaml: set input_dir, output_dir, and add API keys

# 4. Run
uv run ocr-pipeline --config config.yaml
```

That's it. The pipeline discovers all PDFs under `input_dir`, processes them, and writes markdown to `output_dir/`.

---

## Features

- **Multi-engine ensemble** — Marker (local, free), Surya 2 (91 languages, layout + tables), Mathpix (API, math-specialized), Google Document AI (API, enterprise). Engines run in parallel.
- **VLM merge** — Gemini 2.5 Flash (default) or Claude reads all engine outputs plus the page image and produces a final clean transcription. Configurable profiles and system prompts — 7 pre-built profiles for different document types (theological, academic, Irish hagiography, mathematical, legal, citation-focused, general), or use a custom system prompt. Corrects OCR errors, resolves disagreements, preserves formatting.
- **Formatting preservation** — Footnotes (numbers, asterisks, daggers), italics, bold, tables (as markdown), and all special characters are preserved verbatim.
- **Table extraction** — VLM instructed to output pipe-delimited markdown tables for all tabular content.
- **GROBID metadata** — Extract title, authors, DOI, journal, volume, year. Injected as YAML frontmatter in per-document output.
- **Checkpoint & resume** — Stop and restart at any time. Progress is saved per-page. Checkpoints are keyed by file path + size + modification time (not SHA256), so re-downloaded files are matched correctly.
- **Budget tracking** — Set a cap in dollars. The pipeline refuses new API work when cumulative cost exceeds the limit.
- **Self-healing** — Built-in post-processing cleans soft hyphens, em-dash line breaks, whitespace, and ligatures.
- **MCP server** — 4 tools (`ocr_pdf`, `ocr_page`, `ocr_status`, `ocr_metadata`) for opencode agents.
- **CLI + library API** — Use as a `uvx` command or `from ocr_pipeline import Pipeline` in Python.
- **Configurable** — YAML config with environment variable and opencode provider overrides.

---

## Installation

### Prerequisites

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** (recommended) or pip

### Basic install

```bash
cd ocr_pipeline/
uv sync
```

This installs the core dependencies (PyMuPDF, tenacity, PyYAML, tqdm, requests, Anthropic SDK, Google Gemini SDK, Google Document AI, Pillow).

### Installing Marker (optional but recommended)

```bash
uv sync --extra marker
```

Marker provides free, high-quality OCR that runs entirely on your machine. It requires PyTorch.

### Installing Surya 2 (optional)

```bash
uv sync --extra surya2
```

Surya 2 is a 650M-param VLM that does OCR, layout analysis, table detection, and reading order in one pass. 91 languages, 83.3% on olmOCR-bench.

### System Dependencies

| Component | macOS | Ubuntu / Debian | Windows |
|---|---|---|---|
| **PyMuPDF** | pre-built wheel | pre-built wheel | pre-built wheel |
| **Marker (PyTorch)** | MPS acceleration built-in | CUDA toolkit recommended for GPU | CPU-only (CUDA optional) |
| **Marker system libs** | none | `sudo apt install libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev` | none |
| **Google Document AI** | `pip install google-cloud-documentai` | same | same |

### Apple Silicon (M1/M2/M3/M4)

Marker works with MPS (Metal Performance Shaders) acceleration on Apple Silicon. For large documents, you may need to set:

```bash
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0
```

This prevents PyTorch from hitting its default memory limit on MPS.

### Ubuntu / Debian

```bash
# Required for OpenCV (Marker dependency)
sudo apt install libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev
```

GPU acceleration requires NVIDIA CUDA toolkit. See [PyTorch installation guide](https://pytorch.org/get-started/locally/).

### Troubleshooting

| Problem | Solution |
|---|---|
| `marker` command not found | Make sure `uv sync --extra marker` ran successfully. Try `uv run marker --version`. |
| CUDA out of memory | Reduce `marker_concurrency` to 1 in config. Process smaller batches. |
| `ImportError: libGL.so.1` | Install system libs: `sudo apt install libgl1-mesa-glx` |
| PyMuPDF import error | `uv sync` should handle this. On some systems: `pip install pymupdf` directly. |
| Slow on macOS | MPS acceleration is on by default. Check `PYTORCH_MPS_HIGH_WATERMARK_RATIO`. |
| `uv: command not found` | Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` |

---

## CLI Usage

### Basic

```bash
# Process with default config file
uv run ocr-pipeline --config config.yaml
```

### CLI arguments (override config file)

```bash
# Choose engines and VLM model
uv run ocr-pipeline --input ./my_pdfs/ --output ./out/ \
  --engines marker,mathpix \
  --vlm-model claude-sonnet-4-6

# Set a budget cap (stops API work when exceeded)
uv run ocr-pipeline --input ./pdfs/ --budget 50.0

# Content-type hints for better VLM accuracy
uv run ocr-pipeline --input ./pdfs/ \
  --content-type theological \
  --column-layout dual \
  --langs en,la

# Use a document profile for better accuracy
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --content-type irish_hagiography --langs en,gle,la

# Dry run — list files without processing
uv run ocr-pipeline --input ./pdfs/ --dry-run

# Test mode — first 3 pages only
uv run ocr-pipeline --input ./pdfs/ --test

# Resume is automatic — the pipeline detects existing checkpoints and
# picks up where it left off. No special flag needed.
```

### Full CLI reference

```
Usage: ocr-pipeline [OPTIONS]

  --config PATH         Path to config.yaml (default: config.yaml)
  --input PATH          PDF input directory (overrides config)
  --output PATH         Output directory (overrides config)
  --engines LIST        Comma-separated: marker,mathpix,google_doc_ai
  --vlm-model MODEL     VLM model for merge (gemini-2.0-flash-001, claude-haiku-4-5, etc.)
  --budget FLOAT        Budget cap in USD
  --content-type TYPE   general, theological, mathematical, legal
  --column-layout TYPE  single, dual, auto
  --langs LIST          Comma-separated language codes (en,la,de,fr)
  --dry-run             List PDFs without processing
  --test                Process only first 3 pages
  --workers N           Max parallel workers (default: 4)
```

---

## Library Usage

```python
from pathlib import Path
from ocr_pipeline import Pipeline, PipelineConfig

config = PipelineConfig(
    input_dir=Path("./my_pdfs/"),
    output_dir=Path("./output/"),
    engines=["marker", "mathpix"],
    vlm_model="claude-sonnet-4-6",
    budget_cap_usd=50.0,
    postprocess_enabled=True,
)

pipeline = Pipeline(config)
pipeline.run()

# Process a single file
pipeline.process_one(Path("./my_pdfs/single_doc.pdf"))

# Check statistics after completion
print(pipeline.stats)
# {"pages_processed": 342, "pages_failed": 3, "cost_usd": 12.45, ...}
```

---

## Configuration

### `config.yaml` fields

| Field | Type | Default | Description |
|---|---|---|---|
| `input_dir` | path | `./pdfs/` | Directory containing PDFs to process |
| `output_dir` | path | `./output/` | Where processed markdown is written |
| `checkpoint_dir` | path | `output_dir/.checkpoint/` | Checkpoint storage for resume |
| `engines` | list[str] | `["marker"]` | OCR engines to run |
| `vlm.enabled` | bool | `true` | Enable VLM merge step |
| `vlm.model` | str | `gemini-2.0-flash-001` | VLM model ID |
| `vlm.fallback_model` | str | `claude-sonnet-4-6` | Fallback if primary fails |
| `vlm.agreement_threshold` | float | `0.97` | Skip VLM when engines agree |
| `vlm.max_tokens` | int | `8192` | Max tokens for VLM response |
| `vlm.system_prompt` | str | `""` | Custom prompt (empty = built-in) |
| `render_dpi` | int | `300` | DPI for PDF → PNG rendering |
| `postprocess.enabled` | bool | `true` | Run cleanup on text-extractable pages |
| `postprocess.steps` | list[str] | all five | Which cleanup steps to run |
| `budget_cap_usd` | float | `null` | Dollar cap (null = no limit) |
| `engine_cost_per_page` | dict | see below | Per-page cost estimates |
| `max_workers` | int | `4` | Parallel workers |
| `marker_concurrency` | int | `1` | Marker parallel limit |
| `max_retries` | int | `3` | API call retries |
| `retry_base_delay_sec` | float | `1.0` | Initial retry delay |
| `retry_max_delay_sec` | float | `60.0` | Maximum retry delay |
| `api_timeout_sec` | float | `120.0` | Per-call timeout |
| `content_type` | str | `"general"` | Content hint for VLM prompt. One of: `general`, `theological`, `academic`, `mathematical`, `legal`, `citation_focused`, `irish_hagiography` |
| `column_layout` | str | `"auto"` | Column layout hint |
| `languages` | list[str] | `["en"]` | Document languages. Language hints are passed to OCR engines (Marker, Surya2) for improved character recognition accuracy. |

### Environment variable overrides

All API keys and settings can be set via environment variables (which take precedence over the config file):

```bash
export MATHPIX_APP_ID="your_id"
export MATHPIX_APP_KEY="your_key"
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AIza..."
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

---

## Document Profiles

Pre-built system prompt profiles tailored to specific document types. Profiles control how the VLM merge step handles formatting, citations, languages, and special characters.

| Profile | Content Type | Description |
|---|---|---|
| theological_journal | theological | 1950s-1970s theological journal with ecclesiastical Latin, dual-column, footnotes |
| academic | academic | Generic academic publication — preserves citations, DOIs, footnotes |
| irish_hagiography | academic | Modern Irish hagiography dictionary — preserves fada diacritics (á,é,í,ó,ú), English/Irish/Latin |
| mathematical | mathematical | Scientific paper — LaTeX math mode for equations |
| legal | legal | Legal documents — preserves section symbols and statute references |
| citation_focused | citation_focused | Citation-rich documents — preserves every reference verbatim |
| general | general | Generic document — no project-specific assumptions |

Select a content type via `--content-type` CLI flag or `content_type` in config.yaml. You can also provide a fully custom system prompt via `vlm.system_prompt` in config.yaml.

---

## Engine Overview

| Engine | Type | Cost | Best For | Notes |
|---|---|---|---|---|
| **Marker** | Local | Free | General documents | Requires PyTorch. Good accuracy on most PDFs. |
| **Mathpix** | API | $0.005/page | Math-heavy PDFs | Best math/equation OCR available. Free tier: 1000 pages/month. |
| **Google Document AI** | API | $0.0015/page | Enterprise, forms | Google Cloud processor setup required. Free tier: 500 pages/month. |
| **Surya 2** | Local | Free | Coming soon | Next-generation local OCR. Not yet integrated. |

Use Marker as your default. Add Mathpix for math-heavy documents. Use Google Document AI for forms or when you need Google's enterprise OCR quality.

---

## Obtaining API Keys

### Mathpix

1. Go to https://mathpix.com
2. Sign up for an account
3. Get your App ID and App Key from the dashboard
4. Free tier: 1000 pages/month

Set in config.yaml:
```yaml
mathpix_app_id: "your_app_id"
mathpix_app_key: "your_app_key"
```

### Google Gemini (VLM merge)

1. Go to https://aistudio.google.com
2. Sign in with your Google account
3. Click "Get API Key"
4. Free tier: 1500 requests/day

Set in config.yaml:
```yaml
gemini_api_key: "AIza..."
```

Or via environment: `export GEMINI_API_KEY="AIza..."`

### Anthropic Claude (VLM merge alternative)

1. Go to https://console.anthropic.com
2. Sign up and get an API key
3. Pay-as-you-go pricing

Set in config.yaml:
```yaml
anthropic_api_key: "sk-ant-..."
```

### Google Document AI

1. Go to https://cloud.google.com/document-ai
2. Create a project (or use an existing one)
3. Set up a Document AI processor (OCR processor type)
4. Note your project ID and processor ID
5. Free tier: 500 pages/month

Set in config.yaml:
```yaml
google_cloud_project: "your-project-id"
google_processor_id: "your-processor-id"
```

---

## Architecture

```
                     ┌──────────────────────┐
                     │    PDF Documents      │
                     │    (input_dir)        │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │     Renderer          │
                     │  PDF → PNG (300 DPI) │
                     │  + text extraction    │
                     └──────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
     ┌────────▼──────┐  ┌──────▼──────┐  ┌───────▼────────┐
     │    Marker      │  │   Mathpix   │  │ Google Doc AI  │
     │   (local)      │  │   (API)     │  │    (API)       │
     └────────┬───────┘  └──────┬──────┘  └───────┬────────┘
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                     ┌──────────▼───────────┐
                     │    VLM Merge          │
                     │  Gemini / Claude      │
                     │  reads image + all     │
                     │  engine outputs       │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │   Post-Processing     │
                     │  soft hyphens,        │
                     │  whitespace, etc.     │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │    Output             │
                     │  page_NNNN_final.md   │
                     │  (output_dir)         │
                     └───────────────────────┘
```

1. **Renderer** converts each PDF page to a PNG image and attempts fast text extraction.
2. **Engines** run in parallel: Marker (local), Mathpix (API), Google Doc AI (API). Each produces its best transcription.
3. **VLM Merge** sends the page image and all engine outputs to Gemini or Claude, which produces a single corrected markdown transcription.
4. **Post-Processing** cleans up text-extractable pages (soft hyphens, whitespace, ligatures).
5. **Output** is one markdown file per page, plus per-PDF concatenation.

Checkpoint data is stored at each step so the pipeline can be resumed from any point.

---

## Development

### Setup

```bash
cd ocr_pipeline/
uv sync --extra marker

# Run linting
uv run ruff check src/

# Run type checking
uv run mypy src/

# Run tests
uv run pytest tests/ -v
```

### Project structure

```
ocr_pipeline/
├── pyproject.toml
├── config.example.yaml
├── README.md
├── CONTRIBUTING.md
├── src/
│   └── ocr_pipeline/
│       ├── __init__.py
│       ├── config.py          # PipelineConfig, ConfigLoader
│       ├── models.py          # PageStatus, EngineOutput, PageResult, etc.
│       ├── errors.py          # Domain-specific exceptions
│       ├── pipeline.py        # Orchestrator (batch 2)
│       ├── checkpoint.py      # Checkpoint manager (batch 2)
│       ├── renderer.py        # PDF → PNG rendering (batch 2)
│       ├── extractor.py       # Text extraction fast path (batch 2)
│       ├── merger.py          # VLM merge (batch 2)
│       ├── postprocess.py     # Built-in cleanup pipeline (batch 2)
│       ├── costing.py         # Budget tracking (batch 2)
│       ├── progress.py        # Progress bar + ETA (batch 2)
│       ├── cli.py             # CLI entry point (batch 3)
│       ├── engines/
│       │   ├── __init__.py
│       │   ├── base.py        # OcrEngine Protocol + retry decorator
│       │   ├── marker.py
│       │   ├── mathpix.py
│       │   └── google_doc_ai.py
│       └── adapters/
│           ├── __init__.py
│           └── paper_source.py  # PaperSource adapter stub (planned)
└── tests/
    ├── test_pipeline.py
    ├── test_checkpoint.py
    └── test_postprocess.py
```

---

## License

MIT — see [LICENSE](LICENSE) in the repository root.
