# OCR Pipeline

**Multi-engine OCR with VLM merge for PDF documents.**

Multiple OCR engines run in parallel on each page. A Vision Language Model (Gemini or Claude) reads the page image and all engine outputs, then writes a single clean markdown transcription — correcting errors, resolving disagreements, and preserving document structure.

Built-in checkpoint/resume means you can stop and restart without losing progress. Budget tracking prevents surprise API bills. Every API call gets exponential-backoff retry. The pipeline is both a CLI tool and a Python library.

---

## Quickstart

```bash
# 1. Clone the package
git clone https://github.com/jacobhgruber-dev/ocr-pipeline.git
cd ocr-pipeline

# 2. Install
uv sync

# 3. Try it (no config file needed for basic use)
uv run ocr-pipeline --input ./pdfs/ --output ./out/ --profile general

# Or use Claude instead of Gemini (better for diacritics and citations):
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --profile general --vlm-model claude-sonnet-5

# For more options, see what's available:
uv run ocr-pipeline --list-profiles

# Alternative: use a config file for repeatable runs
cp config.example.yaml config.yaml
# Edit config.yaml: set input_dir, output_dir, and add API keys

# Then:
uv run ocr-pipeline --config config.yaml
```

That's it. The pipeline discovers all PDFs under `input_dir`, processes them, and writes markdown to `output_dir/`.

---

## Discovering What's Available

Before configuring, explore what the pipeline offers:

```bash
# List all document profiles with suggested engines and VLM models
uv run ocr-pipeline --list-profiles

# List all OCR engines with requirements and guidance
uv run ocr-pipeline --list-engines

# List 53 supported language codes
uv run ocr-pipeline --list-languages

# List languages supported by a specific engine
uv run ocr-pipeline --list-languages-for marker

# See what would run without processing (safe preview)
uv run ocr-pipeline --input ./pdfs/ --output ./out/ --dry-run
```

---

## Choosing a Profile

Not sure which profile to use? Match your document to this table:

| Your document... | Use this profile | What you get | Budget |
|---|---|---|---|---|
| Letters, reports, novels, general text | `general` | Clean markdown, basic formatting | Free with Gemini |
| Academic paper with citations and footnotes | `academic` | Citation preservation (all styles), DOIs, abstracts, author affiliations | Free (best with Claude) |
| Math, physics, chemistry papers | `mathematical` | LaTeX math mode, blackboard bold, theorem/proof blocks, equation numbers | Free with Gemini |
| Legal documents, contracts, statutes | `legal` | Section symbols, statute references, case citations, signature blocks. Add google_doc_ai engine for forms. | Free (best with Claude) |
| Technical manuals, datasheets, specs | `technical` | Callout boxes, tables, tolerances, code blocks. Add google_doc_ai engine for structured layouts. | Free with Gemini |
| Books (fiction, textbooks, reference) | `books` | Front/back matter, epigraphs, dialogue, scene breaks, index entries | Free with Gemini |
| Chinese/Japanese/Korean documents | `general` or `academic` + `--vlm-model claude-sonnet-5` | CJK ideograph preservation (Gemini fails on these scripts) | Paid (Claude only)

> **Model notes:** "(best with Claude)" means Claude improves citation or diacritic accuracy
> but Gemini works fine for most pages. Only CJK scripts REQUIRE Claude — Gemini
> produces garbled output on Chinese/Japanese/Korean. For all other scripts (including
> Cyrillic, Greek, and Latin with diacritics), Gemini is equal or better.

### By budget

**$0 budget** — free-only mode:
```bash
uv run ocr-pipeline --profile general --no-vlm --input ./pdfs/ --output ./out/
```
No API keys needed. Uses Marker (or Marker+Surya2) locally. VLM merge disabled.

**Free tier** (Gemini free tier: 1500 req/day):
```bash
uv run ocr-pipeline --profile general --input ./pdfs/ --output ./out/
```
Add any languages your document uses: `--langs en,fr,de`

**Best quality** (adds Claude for critical profiles):
```bash
uv run ocr-pipeline --profile academic --vlm-model claude-sonnet-5 \
  --input ./pdfs/ --output ./out/
```
Profiles marked "best with Claude" above benefit from it for precision on structured text.

**If you're not sure**, start here:
```bash
uv run ocr-pipeline --profile general --input ./pdfs/ --output ./out/ --test
```
This processes the first 3 pages as a trial. Check the output, then adjust the profile and re-run.

---

## Features

- **Multi-engine ensemble** — Marker (local, free), Surya 2 (91 languages, layout + tables), Mathpix (API, math-specialized), Google Document AI (API, enterprise). Engines run in parallel.
- **VLM merge** — Gemini 2.5 Flash (default) or Claude reads all engine outputs plus the page image and produces a final clean transcription. Configurable profiles and system prompts — 6 pre-built profiles for different document types (general, academic, mathematical, legal, technical, books), or use a custom system prompt. Corrects OCR errors, resolves disagreements, preserves formatting.
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
  --vlm-model claude-sonnet-5

# Set a budget cap (stops API work when exceeded)
uv run ocr-pipeline --input ./pdfs/ --budget 50.0

# Use a document profile for better accuracy
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --profile academic --langs en,la

# Override profile suggestions
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --profile academic --engines mathpix --vlm-model claude-sonnet-5

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

  --config PATH          Path to config.yaml (default: config.yaml)
  --input PATH           PDF input directory
  --output PATH          Output directory
  --engines LIST         Comma-separated: marker,mathpix,surya2,google_doc_ai
  --vlm-model MODEL      VLM model for merge (gemini-2.5-flash, claude-sonnet-5, etc.)
  --no-vlm               Disable VLM merge
  --vlm-agreement FLOAT  Agreement threshold to skip VLM (default: 0.97)
  --budget FLOAT         Budget cap in USD
  --profile NAME         Document profile: general, academic, mathematical,
                         legal, technical, books
  --column-layout TYPE   single, dual, auto
  --langs LIST           Comma-separated language codes (en, de, fr, la, gle, etc.)
  --dpi N                Render DPI (default: 300)
  --workers N            Max parallel workers (default: 4)
  --marker-concurrency N Max concurrent Marker subprocesses (default: 1)
  --max-retries N        Max API retries (default: 3)
  --retry-base-delay SEC Initial retry delay in seconds (default: 1.0)
  --retry-max-delay SEC  Max retry delay in seconds (default: 60.0)
  --timeout SEC          API timeout in seconds (default: 120.0)
  --marker-venv PATH     Path to Marker virtual environment

  --test                 Process only first 3 pages per PDF
  --dry-run              List PDFs without processing
  --no-postprocess       Skip post-processing cleanup
  --verbose              Verbose logging (DEBUG level)

  --list-profiles        List all document profiles with suggestions
  --list-engines         List all OCR engines with requirements
  --list-languages       List all supported language codes
  --list-languages-for ENGINE  List languages supported by a specific engine
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
    vlm_model="claude-sonnet-5",
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
| `vlm.fallback_model` | str | `claude-sonnet-5` | Fallback if primary fails |
| `vlm.agreement_threshold` | float | `0.97` | Skip VLM when engines agree |
| `vlm.max_tokens` | int | `8192` | Max tokens for VLM response |
| `vlm.system_prompt` | str | `""` | Custom prompt (empty = built-in) |
| `render_dpi` | int | `300` | DPI for PDF → PNG rendering |
| `postprocess.enabled` | bool | `true` | Run cleanup on text-extractable pages |
| `postprocess.steps` | list[str] | all five | Which cleanup steps to run |
| `budget_cap_usd` | float | `null` | Dollar cap (null = no limit) |
| `engine_cost_per_page` | dict | see below | Per-page cost estimates |
| `max_workers` | int | `4` | Parallel workers per PDF |
| `marker_concurrency` | int | `1` | Marker parallel limit |
| `pdf_concurrency` | int | `2` | PDFs processed in parallel (large batches) |
| `max_retries` | int | `3` | API call retries |
| `retry_base_delay_sec` | float | `1.0` | Initial retry delay |
| `retry_max_delay_sec` | float | `60.0` | Maximum retry delay |
| `api_timeout_sec` | float | `120.0` | Per-call timeout |
| `profile` | str | `"general"` | Document profile for VLM prompt. One of: `general`, `academic`, `mathematical`, `legal`, `technical`, `books` |
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

### VLM Model Reference

| Model | Provider | Cost (input/output per 1M tokens) | Best for |
|---|---|---|---|---|
| `gemini-2.5-flash` | Google | $0.15 / $0.60 | Default — best for Latin, Cyrillic, Greek, and LaTeX math |
| `gemini-2.0-flash` | Google | $0.10 / $0.40 | Cheapest option |
| `gemini-2.5-pro` | Google | $1.25 / $10.00 | Higher quality, larger context |
| `claude-sonnet-5` | Anthropic | $3.00 / $15.00 | CJK and high-precision citations (see note below) |
| `claude-haiku-4-5` | Anthropic | $1.00 / $5.00 | **Recommended for CJK** — 3x cheaper than Sonnet, equal quality |
| `claude-3.5-haiku` | Anthropic | $1.00 / $5.00 | Older fast Claude |
| `claude-3.5-sonnet` | Anthropic | $3.00 / $15.00 | Older quality Claude |

> **Script awareness:** Testing across Latin, Cyrillic, Greek, CJK, and French
> diacritics shows that model quality is **script-dependent**. Gemini 2.5 Flash
> handles most scripts perfectly but fails on Chinese/Japanese/Korean. Claude
> handles CJK perfectly but replaces Cyrillic with Latin lookalikes. If your
> document contains multiple scripts, run a test page first to verify output.
> 
> **Arabic/Persian/Urdu (RTL scripts):** Not currently supported by Marker or
> Surya2 OCR engines. Requires Google Document AI with Arabic processor 
> configuration (not included in default setup).

### Script Support at a Glance

| Script | Model to Use | Notes |
|---|---|---|
| Latin, Cyrillic, Greek | gemini-2.5-flash | Perfect — free tier available |
| Chinese, Japanese, Korean | claude-haiku-4-5 | Gemini produces garbled or awkward output. Haiku is 3x cheaper than Sonnet with equal CJK quality |
| Arabic, Persian, Urdu | Google Doc AI only | Marker/Surya don't support RTL; needs Google Cloud setup |

---

## Common Recipes

Each scenario below shows the recommended command for a specific document type.
All examples assume you've set up API keys in `config.yaml` (or as environment variables).

### General document (newspaper, report, book chapter)

```bash
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --profile general --langs en
```

**What it does:** Runs Marker (free, local) on all PDFs. Gemini-2.5-flash merges
the results. Good for 90% of documents.

**Estimated cost:** ~$0.0002/page (VLM only)

### Multilingual academic paper

```bash
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --engines marker,mathpix \
  --profile academic --langs en,de,fr,la
```

**What it does:** Marker + Mathpix handle text and equations. The academic profile
preserves citations, DOIs, and footnotes in CMOS 18 format. Language hints
improve accuracy for non-English text.

### Technical document (manual, datasheet, spec)

```bash
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --engines marker,google_doc_ai \
  --profile technical --langs en
```

**What it does:** Marker + Google Document AI handle structured tables, callout
boxes, and revision tables. The technical profile preserves tolerances, part
numbers, units, and code blocks.

### Books (fiction, textbooks, reference)

```bash
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --profile books --langs en
```

**What it does:** Marker handles the prose and occasional tables/illustrations.
The books profile preserves front/back matter, epigraphs, dialogue, scene
breaks, and cross-references.

### Math-heavy papers (equations, LaTeX)

```bash
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --engines mathpix,marker \
  --profile mathematical --langs en
```

**What it does:** Mathpix handles equation OCR (its specialty), Marker provides
a fallback for plain text. The mathematical profile instructs the VLM to use
LaTeX math mode ($...$ inline, $$...$$ display) for all equations.

### Citation-rich document (bibliography, footnotes)

```bash
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --engines marker,mathpix --profile academic \
  --langs en,la --vlm-model claude-sonnet-5
```

**What it does:** The academic profile instructs the VLM to preserve every
citation verbatim — footnotes, DOIs, author names, page ranges. Claude is used
for its superior precision on structured citation text.

### Free-only pipeline (no API keys needed)

```bash
# Single engine (fastest):
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --engines marker --no-vlm --langs en

# Two engines (more accurate, uses more RAM):
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --engines marker,surya2 --no-vlm --langs en
```

**What it does:** Uses Marker and/or Surya2 (both local, free). VLM merge is
disabled so no Gemini/Claude API key is needed. Marker is faster and lighter;
add Surya2 for 91-language support and better layout analysis (but it uses
more memory). Output is raw engine text after post-processing cleanup.

**Estimated cost:** $0.00

### Cost-sensitive: cap your spending

```bash
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --engines marker,mathpix --budget 5.00
```

**What it does:** Sets a $5.00 budget cap. The pipeline tracks cumulative cost and
refuses new API work when the limit is exceeded. VLM merge is skipped; engine
output is used directly instead.

### Test before committing (first 3 pages only)

```bash
uv run ocr-pipeline --input ./pdfs/ --output ./out/ \
  --engines marker --test
```

**What it does:** Processes only the first 3 pages of each PDF. Good for quickly
checking quality before running a full batch.

---

## Document Profiles

Pre-built system prompt profiles tailored to specific document types. Profiles control how the VLM merge step handles formatting, citations, languages, and special characters.

| Profile | Description |
|---|---|
| general | Generic document — no project-specific assumptions. 15 rules covering tables, figures, multi-column, headers/footers, lists, and code blocks. |
| academic | Academic publication — preserves citations (all styles), DOIs, abstracts, author affiliations, footnotes, tables with notes, and equations. |
| mathematical | Mathematical paper — LaTeX math mode, blackboard bold, calligraphic letters, theorem/proof blocks, equation numbers. |
| legal | Legal documents — section symbols, statute references, case citations, paragraph hierarchy, signature blocks, defined terms. |
| technical | Technical/engineering — callout boxes, revision tables, tolerances, part numbers, code blocks with syntax hints, diagrams, procedure steps. |
| books | Books — front/back matter, block quotes, epigraphs, dialogue, scene breaks, illustrations with captions, cross-references, multi-column layout. |

Select a profile via `--profile` CLI flag or `profile` in config.yaml. You can also provide a fully custom system prompt via `vlm.system_prompt` in config.yaml. Create custom profiles by adding YAML files to the `./profiles/` directory (see `profiles/README.md`).

---

## Engine Overview

| Engine | Type | Cost | Best For | Notes |
|---|---|---|---|---|
| **Marker** | Local | Free | General documents | Requires PyTorch. Good accuracy on most PDFs. |
| **Tesseract** | Local | Free | Arabic/RTL, Cyrillic, fallback | The most widely deployed OCR engine. 6x faster than Marker for Cyrillic. Only working engine for Arabic. |
| **Mathpix** | API | $0.005/page | Math-heavy PDFs | Best math/equation OCR available. Free tier: 1000 pages/month. |
| **Google Document AI** | API | $0.0015/page | Enterprise, forms | Google Cloud processor setup required. Free tier: 500 pages/month. |
| **Surya 2** | Local | Free | Multilingual documents, layout analysis | 91-language VLM OCR. Requires `uv sync --extra surya2`. |
| **GROBID** | Local (Docker) | Free | Academic metadata extraction | Extracts title, authors, DOI, journal metadata. `docker run -p 8070:8070 lfoppiano/grobid:0.8.1` |

Use Marker as your default. Add Tesseract for Arabic/RTL scripts or as a fallback (recommended for general + books profiles). Add Mathpix for math-heavy documents.

---

## Obtaining API Keys

**You don't need any API keys to start.** The pipeline works with Marker and/or
Surya2 (free, local OCR engines) and --no-vlm. You only need keys if you want:

- VLM merge (Gemini key — free tier available at aistudio.google.com)
- Mathpix (for math-heavy documents)
- Google Document AI (for structured documents)

See the "Free-only pipeline" recipe in Common Recipes above.

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

Or via environment:
export MATHPIX_APP_ID="your_app_id"
export MATHPIX_APP_KEY="your_app_key"

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

Or via environment: `export ANTHROPIC_API_KEY="sk-ant-..."`

If you use Gemini (which has a generous free tier), you don't need an Anthropic key at all.

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

Or via environment:
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

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
