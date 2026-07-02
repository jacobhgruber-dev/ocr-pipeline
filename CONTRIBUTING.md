# Contributing to OCR Pipeline

Thanks for your interest in contributing! This document covers setup, how to add engines and VLM models, testing guidelines, and the PR process.

---

## Development Setup

```bash
# Clone and enter the package directory
cd "Academic Research/ocr_pipeline"

# Install with all optional dependencies
uv sync --extra marker

# Run tests to confirm everything works
uv run pytest tests/ -v
```

### Code quality tools

```bash
# Linting (ruff — zero warnings required)
uv run ruff check src/ tests/

# Formatting
uv run ruff format src/ tests/

# Type checking (mypy)
uv run mypy src/
```

These checks run in CI on every PR. Make sure they pass before submitting.

---

## Project Structure

```
ocr_pipeline/
├── pyproject.toml
├── config.example.yaml
├── README.md
├── CONTRIBUTING.md          ← you are here
├── src/
│   └── ocr_pipeline/
│       ├── __init__.py       # Public API exports
│       ├── config.py         # PipelineConfig dataclass + YAML loader
│       ├── models.py         # Core dataclasses (PageResult, EngineOutput, etc.)
│       ├── errors.py         # Domain-specific exceptions
│       ├── pipeline.py       # Main orchestrator
│       ├── checkpoint.py     # Resumable checkpoint management
│       ├── renderer.py       # PDF → PNG via PyMuPDF
│       ├── extractor.py      # Text extraction fast path
│       ├── merger.py         # VLM merge (Gemini/Claude)
│       ├── postprocess.py    # Text cleanup pipeline
│       ├── costing.py        # Budget tracking
│       ├── progress.py       # tqdm progress bar
│       ├── cli.py            # CLI entry point (argparse)
│       ├── engines/
│       │   ├── __init__.py   # Engine registry
│       │   ├── base.py       # OcrEngine Protocol + retry decorator
│       │   ├── marker.py     # Marker local OCR engine
│       │   ├── mathpix.py    # Mathpix API engine
│       │   └── google_doc_ai.py  # Google Document AI engine
│       └── adapters/
│           └── paper_source.py  # MCP PaperSource adapter
└── tests/
    ├── test_pipeline.py
    ├── test_checkpoint.py
    ├── test_postprocess.py
    └── ...
```

---

## Adding a New OCR Engine

All OCR engines implement the `OcrEngine` Protocol defined in `engines/base.py`:

```python
class OcrEngine(Protocol):
    """Contract that every OCR engine must fulfill."""

    name: str  # unique identifier, e.g. "my_engine"

    def recognize(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float = 120.0,
        languages: list[str] | None = None,
    ) -> EngineOutput:
        """Run OCR on a single page image.  Must be thread-safe.

        Args:
            image_path: Path to the rendered page image (PNG).
            page_index: Zero-based page number (for logging/checkpointing).
            timeout_sec: Per-call timeout in seconds.
            languages: Optional list of ISO 639-1 language codes to pass to
                       the OCR engine for language-aware recognition.
        """
        ...
```

### Step-by-step

1. **Create your engine file** in `src/ocr_pipeline/engines/`:

   ```python
   # my_engine.py
   from pathlib import Path
   from ocr_pipeline.engines.base import with_api_retry
   from ocr_pipeline.models import EngineOutput

   class MyEngine:
       name = "my_engine"

       def __init__(self, config: "PipelineConfig"):
           self.config = config

       def recognize(self, image_path: Path, page_index: int = 0,
                      timeout_sec: float = 120.0,
                      languages: list[str] | None = None) -> EngineOutput:
           # Your OCR logic here. Language hints improve recognition accuracy.
           ...
           return EngineOutput(engine=self.name, text=result)
   ```

2. **Register the engine** in `src/ocr_pipeline/engines/__init__.py`:

   ```python
   from .my_engine import MyEngine

   ENGINE_REGISTRY = {
       "marker": MarkerEngine,
       "mathpix": MathpixEngine,
       "google_doc_ai": GoogleDocAiEngine,
       "my_engine": MyEngine,  # ← add here
   }
   ```

3. **Add the engine name** to `EngineName` enum in `models.py`:

   ```python
   class EngineName(str, Enum):
       GOOGLE_DOC_AI = "google_doc_ai"
       MATHPIX = "mathpix"
       MARKER = "marker"
       MY_ENGINE = "my_engine"  # ← add here
   ```

4. **Add cost estimate** (optional) — update `engine_cost_per_page` defaults in `config.py`.

5. **Write tests** in `tests/test_my_engine.py`. At minimum:
   - Unit test with a known image → expected text
   - Error handling (network failure, bad input, timeout)
   - Budget tracking (if the engine has API costs)

6. **Add documentation** — update the Engine Overview table in README.md.

### Using the retry decorator

If your engine makes API calls, wrap them with the built-in retry:

```python
from ocr_pipeline.engines.base import with_api_retry

class MyApiEngine:
    def recognize(self, image_path: Path) -> EngineOutput:
        return self._call_api(image_path)

    @with_api_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
    def _call_api(self, image_path: Path) -> EngineOutput:
        # Your API call here
        ...
```

---

## Adding a New VLM Model

VLM merge models are configured by string ID in `config.yaml`. To add a new model:

1. **Add model support** in `merger.py` — The merger should already handle the model string generically via the Anthropic and Google Gemini SDKs. New models from these providers usually work by just setting `vlm.model` to the model ID in config.

2. **For a new provider** (e.g., OpenAI):

   ```python
   # In merger.py, add a branch for the new provider
   if model.startswith("gpt-"):
       return self._merge_openai(image_data, engine_texts)
   ```

   Add the corresponding SDK dependency to `pyproject.toml`.

3. **Update config documentation** — Add the new model to the comments in `config.example.yaml` and the README.

4. **If your new model is tailored to a specific document type**, consider adding a corresponding profile in the `_SYSTEM_PROMPT_TEMPLATES` and `_DOCUMENT_CONTEXT_HINTS` dictionaries in `merger.py`. Each content_type can have a custom system prompt that the merger assembles automatically.

---

## Testing Guidelines

### Test organization

- `tests/` mirrors `src/ocr_pipeline/` structure
- Unit tests: mock all external APIs and file I/O
- Integration tests: use real PDFs (small, committed to `tests/fixtures/`)
- Use `tmp_path` fixture for all output directories

### Running tests

```bash
# All tests
uv run pytest tests/ -v

# Single test file
uv run pytest tests/test_postprocess.py -v

# With coverage
uv run pytest tests/ --cov=src/ocr_pipeline --cov-report=term
```

### What to test

| Component | What to test |
|---|---|
| **Engine** | Correct text output on known image; error handling; retry behavior; budget tracking |
| **Config** | YAML parsing; environment variable overrides; missing file errors; invalid values |
| **Checkpoint** | Save/load round-trip; V1 migration; orphaned entry cleanup |
| **Post-process** | Each cleanup step individually; step combinations; no-op on clean text |
| **Merger** | Correct output format; agreement threshold skip; fallback model activation |
| **Pipeline** | End-to-end on a small PDF; resume from checkpoint; budget cap enforcement |

### Property-based tests

For parsers, math, state machines, or input validation, prefer [Hypothesis](https://hypothesis.readthedocs.io/):

```python
from hypothesis import given, strategies as st

@given(text=st.text())
def test_postprocess_never_crashes(text):
    processor = PostProcessor()
    result = processor.process(text)
    assert isinstance(result, str)
```

---

## Pull Request Process

1. **Open an issue first** describing the change (unless it's a trivial fix).
2. **Branch** from `main`: `git checkout -b feature/my-engine`.
3. **Write tests** before or alongside your code.
4. **Run all checks**:
   ```bash
   uv run ruff check src/ tests/
   uv run mypy src/
   uv run pytest tests/ -v
   ```
5. **Update documentation** — README, config.example.yaml, and this CONTRIBUTING.md as needed.
6. **Submit a PR** with a clear description:
   - What the change does
   - Why it's needed
   - How it was tested
   - Any breaking changes or migration steps

### Commit style

Keep commits atomic. Prefer:

```
engines: add MyEngine with retry and tests
```

over:

```
added engine, fixed something else, updated docs
```

---

## Questions?

Open an issue on the repository or reach out to the maintainers. We're happy to help you get your first contribution merged.
