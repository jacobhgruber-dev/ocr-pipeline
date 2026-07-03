## Summary

Introduce a `DocumentSource` abstraction that encapsulates all format-specific operations (text extraction, page rendering, metadata, page counting). Each supported format gets an implementation. The `Pipeline` is refactored to enumerate multiple file extensions and dispatch through `DocumentSource` rather than calling PyMuPDF directly. `PageProcessor` is updated to accept a `DocumentSource` instead of a raw `pdf_path`, and gains a `source_image` field so image inputs bypass the rendering step entirely. No new OCR path is needed — images flow directly into the existing OCR → VLM-merge pipeline. Text-only formats (EPUB, DOCX, TXT) use the existing text-extraction fast path and skip OCR entirely.

## Mode

Fresh first-principles design — designing the abstraction layer from scratch, anchoring to the existing codebase's shape but not its PDF-specific internals.

## Design Forces

1. **Backward compatibility** — the public API (`Pipeline.process_one()`, `PipelineConfig`, checkpoint format) must not break for existing PDF users.
2. **Minimum viable scope** — the user asked for "optimally ready," not "fully implemented." The architecture must be forward-extensible without overbuilding.
3. **Minimal churn** — existing PDF code in `extractor.py` and `renderer.py` should be delegated to, not rewritten.
4. **Uniform processing model** — all formats should produce the same output structure (per-"page" markdown, document-level concatenation, metadata frontmatter).
5. **No new dependencies for the PDF path** — EPUB/DOCX/TXT libraries are optional extras; the core pipeline must not require them.

## Approaches Considered

### Option A: Minimal — detect in `process_one()`, branch internally

Keep `run()` globbing `*.pdf` only. In `process_one()`, detect the file extension, branch on format, and call format-specific functions inline.

- **Pros**: Smallest diff. No new files. Quick to implement.
- **Cons**: `process_one()` becomes a 300-line switch statement. Every new format adds more branches. No abstraction to test against. Metadata flow is duplicated. `PageProcessor` still coupled to `pdf_path`. Hard to extend without further surgery.

### Option B: DocumentSource abstraction (RECOMMENDED)

Introduce a `DocumentSource` ABC with format-specific implementations. Pipeline and PageProcessor consume the abstraction instead of raw paths.

- **Pros**: Clean separation of concerns. Each format is an isolated module. `PageProcessor` becomes format-agnostic. Testable in isolation. Extensible — adding a new format means implementing one class. Existing PDF logic is delegated to, not rewritten.
- **Cons**: More files. New abstraction to learn. Slightly more indirection.

### Option C: Convert everything to PDF first

Use external tools (pandoc, libreoffice, img2pdf) to convert non-PDF formats to PDF, then run the existing pipeline unchanged.

- **Pros**: Zero pipeline changes. Reuses everything.
- **Cons**: Loses format-native metadata. EPUB chapter structure is flattened. Conversion quality varies. Adds heavy external dependencies (LibreOffice, pandoc). Doubles disk usage. User explicitly said EPUB should yield structured chapters, not a flattened PDF.

## Recommendation

**Option B — `DocumentSource` abstraction.** This is the "optimally ready" approach: it adds the right abstraction at the right level of generality without overbuilding.

### What the codebase looks like after

**New files:**

```
src/ocr_pipeline/sources/
├── __init__.py          # DocumentSource ABC + detect() factory + format registry
├── pdf.py               # PdfSource — delegates to existing extractor.py/renderer.py
├── epub.py              # EpubSource — ebooklib + bs4 for HTML chapter extraction
├── docx.py              # DocxSource — python-docx for text + properties
├── txt.py               # TxtSource — direct read + chardet encoding detection
└── image.py             # ImageSource — Pillow for EXIF, file-as-render
```

**Modified files:**

| File | Changes |
|------|---------|
| `pipeline.py` | `run()` globs multiple extensions. `process_one()` accepts `DocumentSource`. `_process_single_page()` uses `source`. `_extract_metadata()` adds format-native step before VLM. `_get_or_create_progress()` adds `file_type`. Stats track per-format. |
| `page_processor.py` | `PageContext.pdf_path` → `PageContext.source`. New `source_image: Path \| None` field. `_try_text_extraction()` delegates to `source.extract_text()`. `_render_page()` delegates to `source.render_page()`. `process()` handles image inputs by skipping both extraction and rendering. |
| `models.py` | `PdfProgress` gets `file_type: str = "pdf"`. Docstring updated. `FileIdentity` gets `file_type: str = "pdf"`. |
| `config.py` | New `input_extensions: list[str] \| None = None` (None = auto-detect all). New `input_file_concurrency: int = 2` (renamed from `pdf_concurrency`). `pdf_concurrency` kept as alias for backward compat. |
| `__init__.py` | Export `DocumentSource` and format constants. |

**Untouched files:**

`checkpoint.py`, `renderer.py`, `extractor.py`, `merger.py`, `costing.py`, `errors.py`, `formatter.py`, `postprocess.py`, `progress.py`, `languages.py`, `profiles.py`, all engine files.

## Detailed Design

### 1. `DocumentSource` ABC (`sources/__init__.py`)

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from ..models import MetadataResult


class DocumentSource(ABC):
    """Abstract interface for format-specific document operations.

    Each supported format implements this class, providing:
    - Page counting (how many "pages" to process)
    - Text extraction (returns None if page has no extractable text)
    - Page rendering (produces a PNG for OCR engines)
    - Format-native metadata extraction

    For text-only formats (TXT, EPUB, DOCX), rendering is never needed —
    text extraction always succeeds and the OCR path is skipped.

    For image formats, text extraction always fails, rendering is a no-op
    (the image IS the rendered page), and the full OCR path runs.

    For PDF, both paths exist — extraction for text-rich pages, rendering
    + OCR for image-based pages.
    """

    SUPPORTED_EXTENSIONS: ClassVar[dict[str, str]] = {}  # suffix → format name
    file_path: Path
    file_type: str

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    # --- required overrides ---

    @abstractmethod
    def page_count(self) -> int:
        """Return the number of processable units in this document.

        PDF: ``doc.page_count`` from PyMuPDF.
        EPUB: number of spine items (chapters).
        DOCX: 1 (entire document as one unit).
        TXT: 1.
        Image: 1.
        """
        ...

    @abstractmethod
    def extract_text(self, page_index: int) -> str | None:
        """Extract text from a page. Returns None if not extractable.

        PDF: PyMuPDF ``page.get_text("text")``. May return empty string on
             image-only pages.
        EPUB: HTML body text from chapter at spine index.
        DOCX: All paragraph text from document.
        TXT: Entire file content (page_index is always 0).
        Image: Always returns None (no text to extract).
        """
        ...

    @abstractmethod
    def render_page(self, page_index: int, render_dir: Path, dpi: int = 300) -> Path:
        """Render a page to a PNG file. Returns the path to the PNG.

        PDF: PyMuPDF ``page.get_pixmap()`` at requested DPI.
        EPUB: Not implemented (raises NotImplementedError in MVP).
        DOCX: Not implemented.
        TXT: Not implemented.
        Image: Returns ``self.file_path`` (the image IS the render).
        """
        ...

    @abstractmethod
    def extract_metadata(self) -> MetadataResult:
        """Extract format-native metadata. Returns empty result if unavailable.

        PDF: PyMuPDF metadata dict (title, author).
        EPUB: OPF metadata (title, creator, identifier/ISBN, publisher, date).
        DOCX: core.xml properties (title, creator, modified).
        TXT: Filename-based heuristics (title from filename, date from mtime).
        Image: EXIF data via Pillow.
        """
        ...

    # --- optional overrides ---

    def can_extract_text(self) -> bool:
        """Whether text extraction is meaningful for this format."""
        return self.file_type not in ("png", "jpg", "jpeg", "tiff", "bmp", "webp")

    def needs_ocr(self) -> bool:
        """Whether this format benefits from OCR processing."""
        return self.file_type in ("pdf", "png", "jpg", "jpeg", "tiff", "bmp", "webp")

    def get_page_label(self, page_index: int) -> str:
        """Human-readable label for a page."""
        return f"page_{page_index + 1:04d}"

    # --- factory ---

    @classmethod
    def detect(cls, file_path: Path) -> DocumentSource:
        """Detect format from file extension and return appropriate source."""
        suffix = file_path.suffix.lower()

        if suffix in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"):
            from .image import ImageSource
            return ImageSource(file_path)
        elif suffix == ".epub":
            from .epub import EpubSource
            return EpubSource(file_path)
        elif suffix == ".docx":
            from .docx import DocxSource
            return DocxSource(file_path)
        elif suffix == ".txt":
            from .txt import TxtSource
            return TxtSource(file_path)
        else:
            # Default to PDF for .pdf and unknown extensions
            from .pdf import PdfSource
            return PdfSource(file_path)

    @classmethod
    def supported_extensions(cls) -> list[str]:
        """Return all supported file extensions for globbing."""
        return [
            "pdf", "epub", "docx", "txt",
            "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp",
        ]
```

### 2. `PdfSource` (`sources/pdf.py`)

Wraps existing `extractor.py` and `renderer.py` with zero logic changes to those modules.

```python
from __future__ import annotations
from pathlib import Path

from . import DocumentSource
from ..extractor import extract_page_text
from ..renderer import get_page_count as _pdf_page_count, render_page as _pdf_render
from ..models import MetadataResult


class PdfSource(DocumentSource):
    file_type = "pdf"

    def page_count(self) -> int:
        return _pdf_page_count(self.file_path)

    def extract_text(self, page_index: int) -> str | None:
        import tempfile
        text, _ = extract_page_text(
            self.file_path, page_index,
            Path(tempfile.gettempdir()),  # we don't need the saved file here
        )
        return text if text.strip() else None

    def render_page(self, page_index: int, render_dir: Path, dpi: int = 300) -> Path:
        return _pdf_render(self.file_path, page_index, render_dir, dpi=dpi)

    def extract_metadata(self) -> MetadataResult:
        """Extract PyMuPDF metadata (title, author) from the PDF."""
        try:
            import fitz
            doc = fitz.open(str(self.file_path))
            meta = doc.metadata
            doc.close()
            return MetadataResult(
                title=meta.get("title", "") or "",
                authors=[meta.get("author", "")] if meta.get("author") else [],
                extraction_method="pdf",
            )
        except Exception:
            return MetadataResult(extraction_method="none")
```

### 3. `EpubSource` (`sources/epub.py`)

Uses `ebooklib` for OPF parsing and chapter enumeration. Uses `beautifulsoup4` for HTML text extraction.

```python
from __future__ import annotations
from pathlib import Path
from typing import Any

from . import DocumentSource
from ..models import MetadataResult


class EpubSource(DocumentSource):
    """EPUB document source. Each spine item (chapter) is one "page"."""

    file_type = "epub"

    def __init__(self, file_path: Path) -> None:
        super().__init__(file_path)
        self._book: Any = None
        self._spine_ids: list[str] = []

    def _load(self) -> None:
        if self._book is not None:
            return
        try:
            import ebooklib
            from ebooklib import epub as epub_lib
        except ImportError:
            raise ImportError(
                "ebooklib is required for EPUB processing. Install with: pip install ebooklib beautifulsoup4"
            )
        self._book = epub_lib.read_epub(str(self.file_path))
        # Collect spine items that reference actual documents
        spine = self._book.spine if hasattr(self._book, 'spine') else []
        items = self._book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
        id_to_item = {item.get_id(): item for item in items}
        for (idref, linear) in spine:
            if idref in id_to_item:
                self._spine_ids.append(idref)
        if not self._spine_ids:
            # Fallback: use all document items
            self._spine_ids = [item.get_id() for item in items]

    def page_count(self) -> int:
        self._load()
        return len(self._spine_ids)

    def extract_text(self, page_index: int) -> str | None:
        self._load()
        if page_index < 0 or page_index >= len(self._spine_ids):
            return None
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError(
                "beautifulsoup4 is required for EPUB text extraction. Install with: pip install beautifulsoup4"
            )
        item_id = self._spine_ids[page_index]
        item = self._book.get_item_with_id(item_id)
        if item is None:
            return None
        html = item.get_content().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text("\n", strip=True) or None

    def render_page(self, page_index: int, render_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("EPUB page rendering is not supported in MVP")

    def extract_metadata(self) -> MetadataResult:
        self._load()
        result = MetadataResult(extraction_method="epub")
        try:
            # OPF metadata is available through ebooklib's get_metadata()
            dc = self._book.get_metadata("DC", "title")
            if dc:
                result.title = dc[0][0] if isinstance(dc[0], tuple) else str(dc[0])
            creators = self._book.get_metadata("DC", "creator")
            result.authors = [
                c[0] if isinstance(c, tuple) else str(c) for c in creators
            ]
            identifiers = self._book.get_metadata("DC", "identifier")
            for id_val in identifiers:
                val = id_val[0] if isinstance(id_val, tuple) else str(id_val)
                if "isbn" in str(val).lower():
                    result.isbn = str(val).split(":")[-1].strip()
                elif "doi" in str(val).lower():
                    result.doi = str(val).split(":")[-1].strip()
            publishers = self._book.get_metadata("DC", "publisher")
            if publishers:
                result.publisher = (
                    publishers[0][0] if isinstance(publishers[0], tuple)
                    else str(publishers[0])
                )
            dates = self._book.get_metadata("DC", "date")
            if dates:
                result.date = (
                    dates[0][0] if isinstance(dates[0], tuple)
                    else str(dates[0])
                )
            languages = self._book.get_metadata("DC", "language")
            if languages:
                result.language = (
                    languages[0][0] if isinstance(languages[0], tuple)
                    else str(languages[0])
                )
            result.document_type = "book"
        except Exception:
            pass
        return result

    def get_page_label(self, page_index: int) -> str:
        return f"chapter_{page_index + 1:04d}"
```

### 4. `DocxSource` (`sources/docx.py`)

```python
from __future__ import annotations
from pathlib import Path

from . import DocumentSource
from ..models import MetadataResult


class DocxSource(DocumentSource):
    file_type = "docx"

    def page_count(self) -> int:
        return 1

    def extract_text(self, page_index: int) -> str | None:
        if page_index != 0:
            return None
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "python-docx is required for DOCX processing. Install with: pip install python-docx"
            )
        doc = Document(str(self.file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs) or None

    def render_page(self, page_index: int, render_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("DOCX page rendering is not supported in MVP")

    def extract_metadata(self) -> MetadataResult:
        try:
            from docx import Document
        except ImportError:
            return MetadataResult(extraction_method="none")
        doc = Document(str(self.file_path))
        props = doc.core_properties
        return MetadataResult(
            title=props.title or "",
            authors=[props.author] if props.author else [],
            language=props.language or "",
            date=str(props.modified) if props.modified else "",
            document_type="document",
            extraction_method="docx",
        )
```

### 5. `TxtSource` (`sources/txt.py`)

```python
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone

from . import DocumentSource
from ..models import MetadataResult


class TxtSource(DocumentSource):
    file_type = "txt"

    def page_count(self) -> int:
        return 1

    def extract_text(self, page_index: int) -> str | None:
        if page_index != 0:
            return None
        # Detect encoding
        encoding = "utf-8"
        try:
            import chardet
            with open(self.file_path, "rb") as f:
                raw = f.read(4096)
            detected = chardet.detect(raw)
            if detected and detected.get("encoding"):
                encoding = detected["encoding"]
        except ImportError:
            pass  # fall back to utf-8

        try:
            return self.file_path.read_text(encoding=encoding, errors="replace")
        except Exception:
            return self.file_path.read_text(encoding="utf-8", errors="replace")

    def render_page(self, page_index: int, render_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("TXT page rendering is not supported in MVP")

    def extract_metadata(self) -> MetadataResult:
        st = self.file_path.stat()
        # Derive title from filename
        title = self.file_path.stem.replace("_", " ").replace("-", " ")
        return MetadataResult(
            title=title,
            date=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            document_type="text",
            extraction_method="txt",
        )
```

### 6. `ImageSource` (`sources/image.py`)

```python
from __future__ import annotations
from pathlib import Path

from . import DocumentSource
from ..models import MetadataResult


class ImageSource(DocumentSource):
    """Image document source. The image file IS the rendered page."""

    file_type: str  # "png", "jpg", etc. — set at init

    IMAGE_TYPES: dict[str, str] = {
        ".png": "png", ".jpg": "jpg", ".jpeg": "jpg",
        ".tiff": "tiff", ".tif": "tiff", ".bmp": "bmp", ".webp": "webp",
    }

    def __init__(self, file_path: Path) -> None:
        super().__init__(file_path)
        suffix = file_path.suffix.lower()
        self.file_type = self.IMAGE_TYPES.get(suffix, "unknown")

    def page_count(self) -> int:
        return 1

    def extract_text(self, page_index: int) -> str | None:
        return None  # Images have no extractable text

    def render_page(self, page_index: int, render_dir: Path, dpi: int = 300) -> Path:
        """Return the image file itself — no rendering needed."""
        return self.file_path

    def extract_metadata(self) -> MetadataResult:
        result = MetadataResult(extraction_method="image", document_type="image")
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            img = Image.open(str(self.file_path))
            exif_data = img.getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    if tag_name == "DateTime":
                        result.date = str(value)
                    elif tag_name == "ImageDescription":
                        result.title = str(value)[:200]
                    elif tag_name == "Artist":
                        result.authors = [str(value)]
            # Also set dimensions in extra
            result.extra = {
                "width": img.width,
                "height": img.height,
                "format": img.format,
            }
        except Exception:
            pass
        return result

    def can_extract_text(self) -> bool:
        return False

    def needs_ocr(self) -> bool:
        return True
```

### 7. `PageContext` changes (`page_processor.py`)

```python
@dataclass
class PageContext:
    page: PageResult
    source: DocumentSource          # was: pdf_path: Path
    output_dir: Path
    render_dir: Path

    # Populated by phases
    png_path: Path | None = None
    source_image: Path | None = None  # NEW: set for image inputs
    engine_outputs: list[EngineOutput] = field(default_factory=list)
    merged_markdown: str = ""
    vlm_raw: str = ""
    vlm_model: str = ""
    agreement: float = 0.0
    cost: float = 0.0
```

### 8. `PageProcessor.process()` refactored flow

```python
def process(self, ctx: PageContext) -> PageContext:
    ctx.page.started_at = now_iso()
    try:
        # Phase 1: text extraction (all text-capable formats)
        if ctx.source.can_extract_text() and self._try_text_extraction(ctx):
            if not self.config.vlm_enabled:
                return ctx
            # VLM enabled but no rendering for non-PDF text formats in MVP
            if not ctx.source.file_type == "pdf":
                logger.debug("VLM merge skipped for %s — not supported in MVP",
                             ctx.source.file_type)
                return ctx
            self._render_page(ctx)
            self._vlm_merge_extracted(ctx)
            ctx.merged_markdown = ctx.page.merged_markdown
            self._save_outputs(ctx)
            ctx.page.status = PageStatus.COMPLETE
            ctx.page.completed_at = now_iso()
            return ctx

        # Phase 2: render to PNG (or use source_image for images)
        if ctx.source_image is not None:
            ctx.png_path = ctx.source_image  # image IS the render
        else:
            self._render_page(ctx)
        ...

        # Phases 3-6: OCR, merge, cost, save (unchanged for PDF and images)
        ...
```

### 9. `_try_text_extraction()` refactored

```python
def _try_text_extraction(self, ctx: PageContext) -> bool:
    try:
        text = ctx.source.extract_text(ctx.page.page_index)
        if text and text.strip():
            if self.config.postprocess_enabled:
                text = self.postprocessor.process(text)
            ctx.page.merged_markdown = text
            ctx.page.has_extractable_text = True
            ctx.page.status = PageStatus.EXTRACTED
            ctx.page.completed_at = now_iso()
            ctx.page.estimated_cost = 0.0
            ctx.cost = 0.0

            # Save via configured formatters
            for fmt_name in self.config.output_formats:
                formatter = get_formatter(fmt_name)
                out_path = ctx.output_dir / f"{ctx.page.page_label}_final{formatter.extension()}"
                out_path.write_text(formatter.format(ctx.page), encoding="utf-8")

            self._save_raw_json(ctx)
            return True
    except Exception:
        pass
    return False
```

### 10. `_render_page()` refactored

```python
def _render_page(self, ctx: PageContext) -> None:
    ctx.png_path = ctx.source.render_page(
        ctx.page.page_index,
        ctx.render_dir,
        dpi=self.config.render_dpi,
    )
```

### 11. Pipeline `run()` refactored

```python
def run(self) -> dict[str, Any]:
    t0 = time.perf_counter()

    # Enumerate files matching configured extensions
    extensions = self.config.input_extensions or DocumentSource.supported_extensions()
    patterns = [f"*.{ext}" for ext in extensions]
    file_paths: list[Path] = []
    for pattern in patterns:
        file_paths.extend(self.config.input_dir.rglob(pattern))
    file_paths = sorted(set(file_paths))  # deduplicate

    if not file_paths:
        logger.warning("No files found in %s", self.config.input_dir)
        return self._build_stats(0.0)

    # Detect document sources
    sources = [DocumentSource.detect(fp) for fp in file_paths]

    # Pre-compute total pages
    total_pages = 0
    for source in sources:
        try:
            total_pages += source.page_count()
        except Exception:
            total_pages += 1

    # Process in parallel (unchanged thread pool logic)
    ...
```

### 12. Metadata extraction refactored

```python
def _extract_metadata(self, source: DocumentSource) -> MetadataResult:
    # 1. Format-native metadata (NEW)
    try:
        result = source.extract_metadata()
        if result.extraction_method not in ("none", "") and (
            result.title or result.doi or result.document_type or result.authors
        ):
            logger.info("Metadata from %s: type=%s, title=%s",
                        source.file_type, result.document_type, result.title[:60])
            return result
    except Exception as exc:
        logger.debug("Format-native metadata failed for %s: %s", source.file_path.name, exc)

    # 2. VLM extraction (existing — works on any file type)
    from .engines.metadata_vlm import VlmMetadataEngine
    try:
        vlm = VlmMetadataEngine(
            vlm_model=self.config.vlm_metadata_model,
            api_key=self.config.gemini_api_key,
            page_count=3,
        )
        result = vlm.extract(source.file_path)
        if result.extraction_method == "vlm" and (result.title or result.document_type):
            logger.info("Metadata via VLM: type=%s, title=%s",
                        result.document_type, result.title[:60])
            return result
    except Exception as exc:
        logger.warning("VLM metadata extraction failed: %s", exc)

    # 3. GROBID (PDF only)
    if source.file_type == "pdf":
        try:
            from .engines.grobid import GrobidEngine
            engine = GrobidEngine(grobid_url=self.config.grobid_url)
            result = engine.extract_metadata(source.file_path, timeout_sec=30)
            result.extraction_method = "grobid"
            if result.title or result.doi:
                logger.info("Metadata via GROBID: title=%s", result.title[:60])
                return result
        except Exception as exc:
            logger.warning("GROBID metadata extraction failed: %s", exc)

    return MetadataResult(extraction_method="none")
```

### 13. Model changes (`models.py`)

```python
@dataclass
class PdfProgress:
    # ...existing fields...
    file_type: str = "pdf"  # NEW: "pdf", "epub", "docx", "txt", "png", "jpg", etc.
```

Add to `to_dict()` / `from_dict()` serialization (with backward-compatible defaults).

### 14. Config changes (`config.py`)

```python
@dataclass
class PipelineConfig:
    # ...existing fields...
    input_extensions: list[str] | None = None  # NEW: None = auto-detect all
    input_file_concurrency: int = 2  # NEW: renamed from pdf_concurrency
```

Add backward compat: `pdf_concurrency` still works as an alias via `__post_init__` or property.

## Processing Flow Per Format

| Format | page_count | extract_text | render_page | OCR engines | VLM merge | Metadata (native) | Metadata (VLM) | Metadata (GROBID) |
|--------|-----------|-------------|-------------|-------------|-----------|-------------------|----------------|-------------------|
| PDF | PyMuPDF count | PyMuPDF → returns text or None | PyMuPDF → PNG | Yes (if no text) | Yes (if multi-engine or VLM-for-extracted) | PyMuPDF dict | Yes | Yes |
| EPUB | Spine items | ebooklib + bs4 → HTML text | N/A (raises) | No | No (MVP) | OPF metadata | Yes | No |
| DOCX | 1 | python-docx → paragraphs | N/A (raises) | No | No (MVP) | Doc properties | Yes | No |
| TXT | 1 | Direct read + chardet | N/A (raises) | No | No (MVP) | Filename heuristics | Yes | No |
| Image | 1 | Always None | returns self (no-op) | Yes | Yes | EXIF | Yes | No |

## New Dependencies (optional extras)

```
[project.optional-dependencies]
epub = ["ebooklib>=0.18", "beautifulsoup4>=4.12"]
docx = ["python-docx>=1.1"]
txt = ["chardet>=5.0"]
```

All new dependencies are `ImportError`-guarded — the pipeline imports them lazily in the source implementations. If a user only processes PDFs, no new packages are required.

## Risks & Mitigations

1. **Checkpoint backward compatibility** — old checkpoint files lack `file_type`. Mitigation: `from_dict()` defaults `file_type="pdf"` when absent. Old checkpoints continue to work.

2. **`pdf_concurrency` field rename** — existing configs may use `pdf_concurrency` in YAML. Mitigation: accept both `input_file_concurrency` and `pdf_concurrency` in YAML loading, with `pdf_concurrency` silently aliased. Log a deprecation warning when the old name is used.

3. **EPUB HTML complexity** — some EPUBs have non-standard HTML (nested tables, JavaScript, SVGs). Mitigation: `beautifulsoup4` `get_text()` is tolerant. Add a `max_text_length` guard to prevent runaway extraction.

4. **Image format support** — Pillow already handles PNG, JPG, TIFF, BMP, WebP. GIF and SVG are intentionally excluded from MVP (GIF is multi-frame, SVG is vector). Mitigation: `DocumentSource.detect()` only registers the supported image extensions.

5. **Large text files** — a multi-GB TXT file could OOM if read entirely. Mitigation: add a `max_text_bytes` config (default 50MB). Files larger than this are chunked or skipped with a warning.

6. **EPUB DRM** — DRM-protected EPUBs will fail to open. Mitigation: `ebooklib` raises on DRM content; catch and surface a clear error message.
