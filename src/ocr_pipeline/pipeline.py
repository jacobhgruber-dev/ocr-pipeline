"""Main pipeline orchestrator — ties together rendering, OCR, VLM merge, and output.

Usage::

    config = PipelineConfig(input_dir=Path("./pdfs"), output_dir=Path("./out"))
    pipeline = Pipeline(config)
    stats = pipeline.run()
    print(stats)

    # Or process a single file (PDF or any supported format):
    pipeline.process_one(Path("./pdfs/document.pdf"))
    pipeline.process_one(DocxSource(Path("./reports/report.docx")))
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from datetime import datetime, timezone

from .checkpoint import CheckpointManager
from .config import PipelineConfig
from .costing import BudgetTracker
from .engines import create_engine
from .engines.base import CircuitBreaker
from .errors import RenderError
from .extractor import extract_page_text
from .merger import (
    DefaultVlmMerger,
    VlmMerger,
)
from .models import (
    EngineName,
    EngineOutput,
    FileIdentity,
    MetadataResult,
    PageResult,
    PageStatus,
    PdfProgress,
)
from .page_processor import PageContext, PageProcessor
from .postprocess import PostProcessor
from .progress import PipelineProgress

logger = logging.getLogger("ocr_pipeline")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class Pipeline:
    """Multi-engine OCR pipeline with VLM merge for PDF and other documents.

    Processes all files matching ``config.input_extensions`` found in
    ``config.input_dir``, using a fast text-extraction path for pages
    with embedded text and a full render→OCR→VLM-merge path for
    image-only pages.
    """

    def __init__(
        self,
        config: PipelineConfig,
        vlm_merger: VlmMerger | None = None,
    ) -> None:
        self.config = config
        self._vlm_merger = vlm_merger or DefaultVlmMerger()

        # Validate language codes early
        from .languages import validate_language_config

        if self.config.languages:
            validate_language_config(self.config.languages)

        # Budget
        self.budget = BudgetTracker(config.budget_cap_usd)

        # Checkpoint
        checkpoint_dir = config.checkpoint_dir or (config.output_dir / ".checkpoint")
        self.checkpoint = CheckpointManager(checkpoint_dir)

        # Post-processor
        self.postprocessor = PostProcessor(
            config.postprocess_steps if config.postprocess_enabled else []
        )

        # Circuit breakers (one per engine, 5 consecutive failures → open)
        self._circuit_breakers: dict[str, CircuitBreaker] = {
            name: CircuitBreaker(threshold=5) for name in config.engines
        }

        # Concurrency
        self._marker_semaphore = threading.Semaphore(config.marker_concurrency)
        self._checkpoint_lock = threading.Lock()

        # Engines (initialized lazily-computed list)
        self.engines: dict[str, Any] = {}
        self._init_engines()

        # Stats
        self._pdfs_processed: int = 0
        self._pdfs_failed: int = 0
        self._pages_processed: int = 0
        self._pages_complete: int = 0
        self._pages_failed: int = 0
        self._total_confidence: float = 0.0

    # ------------------------------------------------------------------
    # engine initialization
    # ------------------------------------------------------------------

    def _init_engines(self) -> None:
        """Initialize OCR engines via the factory.

        Engine failures are non-fatal — the pipeline runs with the subset
        that initialized successfully.
        """
        for name in self.config.engines:
            try:
                engine = create_engine(name, self.config)
                if engine.health_check():
                    self.engines[name] = engine
                    logger.info("Engine %s initialized", name)
                else:
                    logger.warning("Engine %s health check failed — skipped", name)
            except Exception as exc:
                logger.warning("Engine %s unavailable: %s", name, exc)

        if not self.engines:
            logger.warning("No OCR engines available — processing will be limited")

        # Auto-add Tesseract for RTL scripts (Marker/Surya2 don't support them).
        # Tesseract is the only working engine for Arabic, Persian, and Urdu.
        from .languages import is_rtl

        if self.config.languages and any(is_rtl(lang) for lang in self.config.languages):
            if "tesseract" not in self.engines:
                try:
                    engine = create_engine("tesseract", self.config)
                    if engine.health_check():
                        self.engines["tesseract"] = engine
                        logger.info("Auto-added Tesseract — required for RTL script support")
                except Exception as exc:
                    logger.warning("Tesseract unavailable for RTL: %s", exc)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Process all files matching ``config.input_extensions`` in ``config.input_dir``.

        Files are processed in parallel (controlled by ``pdf_concurrency``,
        default 2).  Each file's pages are processed in parallel internally.

        Returns:
            Stats dict with keys ``pdfs_processed``, ``pdfs_failed``,
            ``pages_processed``, ``pages_complete``, ``pages_failed``,
            ``total_cost``, ``duration_sec``.
        """
        t0 = time.perf_counter()

        # Collect all paths matching configured extensions
        ext_list = getattr(self.config, "input_extensions", ["pdf"])
        file_paths: list[Path] = []
        for ext in ext_list:
            ext_clean = ext.lstrip(".")
            file_paths.extend(sorted(self.config.input_dir.rglob(f"*.{ext_clean}")))

        if not file_paths:
            extensions_str = ", ".join(ext_list)
            logger.warning(
                "No files matching extensions [%s] found in %s",
                extensions_str,
                self.config.input_dir,
            )
            return self._build_stats(0.0)

        # Pre-compute total pages for progress reporting
        total_pages = 0
        for fp in file_paths:
            try:
                source = self._build_source(fp)
                total_pages += source.page_count
            except Exception:
                total_pages += 1  # assume at least 1 page
        if self.config.test_mode:
            total_pages = min(total_pages, 3 * len(file_paths))

        logger.info(
            "Found %d file(s) (%d total pages) matching %s in %s",
            len(file_paths),
            total_pages,
            ext_list,
            self.config.input_dir,
        )

        pdf_workers = getattr(self.config, "pdf_concurrency", 2)
        progress = PipelineProgress(total_pages=total_pages, budget=self.budget)
        stats_lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=pdf_workers) as executor:
            future_to_path: dict[Future[dict[str, Any]], Path] = {
                executor.submit(self.process_one, fp): fp for fp in file_paths
            }

            for future in as_completed(future_to_path):
                file_path = future_to_path[future]
                file_stats: dict[str, Any] = {}
                try:
                    file_stats = future.result()
                    with stats_lock:
                        self._pdfs_processed += 1
                        self._pages_processed += file_stats.get("pages_processed", 0)
                        self._pages_complete += file_stats.get("pages_complete", 0)
                        self._pages_failed += file_stats.get("pages_failed", 0)
                except Exception as exc:
                    logger.error("Failed to process %s: %s", file_path.name, exc)
                    with stats_lock:
                        self._pdfs_failed += 1

                pages_done = file_stats.get("pages_processed", 0) + file_stats.get(
                    "pages_skipped", 0
                )
                for _ in range(max(pages_done, 1)):
                    progress.update(0, 0.0)

                with stats_lock:
                    self._total_confidence += file_stats.get("pages_confidence_sum", 0.0)

        progress.close()

        # Concatenate all per-PDF document outputs into a collection file
        try:
            self._produce_collection_output()
        except Exception:
            logger.debug("Failed to produce collection output", exc_info=True)

        duration = round(time.perf_counter() - t0, 1)
        return self._build_stats(duration)

    def process_one(self, file_input: Path | Any) -> dict[str, Any]:
        """Process a single file through the pipeline.

        Args:
            file_input: Either a ``Path`` to a file on disk, or a
                ``DocumentSource`` instance (for programmatic use).

        Returns:
            Per-file stats dict.
        """
        # -- Resolve input to a Path + optional DocumentSource --
        if isinstance(file_input, Path):
            file_path = file_input.resolve()
            source = self._build_source(file_path)
        else:
            # Assume DocumentSource instance
            source = file_input
            file_path = source.path

        file_type = source.source_format
        page_count = source.page_count
        if self.config.test_mode:
            page_count = min(page_count, 3)

        # Build file identity
        try:
            st = file_path.stat()
        except OSError as exc:
            raise RenderError(f"Cannot stat file: {file_path}") from exc

        rel_path = str(file_path.relative_to(self.config.input_dir))
        sha256 = self._compute_sha256(file_path)
        short_sha = sha256[:12]

        file_id = FileIdentity(
            relative_path=rel_path,
            size_bytes=st.st_size,
            mtime_epoch=st.st_mtime,
            sha256=sha256,
            file_type=file_type,
        )

        # Check checkpoint for existing progress
        with self._checkpoint_lock:
            pdfs = self.checkpoint.load()
            existing = pdfs.get(rel_path)

        if existing is not None:
            # If all pages complete, skip
            all_done = all(
                p.status in (PageStatus.COMPLETE, PageStatus.EXTRACTED) for p in existing.pages
            )
            if all_done:
                logger.info("%s: all pages already complete — skipping", short_sha)
                return {
                    "pages_processed": 0,
                    "pages_complete": 0,
                    "pages_failed": 0,
                    "pages_confidence_sum": 0.0,
                }

        # Get or create PdfProgress
        with self._checkpoint_lock:
            pp = self._get_or_create_progress(
                file_id=file_id,
                pdf_path=file_path,
                sha256=sha256,
                short_sha=short_sha,
                rel_path=rel_path,
                page_count=page_count,
            )
            pp.file_type = file_type

        # Output directory for this file
        output_dir = self.config.output_dir / short_sha
        render_dir = output_dir / "renders"
        output_dir.mkdir(parents=True, exist_ok=True)

        pages_processed = 0
        pages_complete = 0
        pages_failed = 0
        pages_confidence_sum = 0.0

        # Collect pages that need processing
        pending = [
            (i, pp.pages[i])
            for i in range(page_count)
            if pp.pages[i].status
            not in (PageStatus.COMPLETE, PageStatus.EXTRACTED, PageStatus.SKIPPED)
        ]

        if not pending:
            logger.info("%s: all %d pages already complete", short_sha, page_count)
            return {
                "pages_processed": 0,
                "pages_complete": 0,
                "pages_failed": 0,
                "pages_confidence_sum": 0.0,
            }

        # Process pending pages with thread pool
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_map: dict[Future[tuple[PageResult, float]], PageResult] = {}

            for page_index, page in pending:
                future = executor.submit(
                    self._process_single_page,
                    file_path,
                    page,
                    output_dir,
                    render_dir,
                    source,
                )
                future_map[future] = page

            for future in as_completed(future_map):
                page = future_map[future]
                try:
                    result_page, cost = future.result()
                    with self._checkpoint_lock:
                        self.checkpoint.update_page(rel_path, result_page)
                    if result_page.status in (PageStatus.COMPLETE, PageStatus.EXTRACTED):
                        pages_complete += 1
                    else:
                        pages_failed += 1
                    pages_processed += 1
                    if result_page.confidence is not None:
                        pages_confidence_sum += result_page.confidence
                    self._log_page(result_page, short_sha)
                except Exception as exc:
                    logger.error(
                        "Page %d of %s failed: %s",
                        page.page_index + 1,
                        short_sha,
                        exc,
                    )
                    page.status = PageStatus.FAILED
                    page.error = str(exc)
                    pages_failed += 1
                    pages_processed += 1
                    with self._checkpoint_lock:
                        self.checkpoint.update_page(rel_path, page)

        # Produce document-level concatenated output (PDF-only for now)
        if file_type == "pdf":
            try:
                self._produce_document_output(file_path, output_dir, short_sha, page_count, source)
            except Exception:
                logger.debug("Skipping document-level output for %s", short_sha, exc_info=True)

        return {
            "pages_processed": pages_processed,
            "pages_complete": pages_complete,
            "pages_failed": pages_failed,
            "pages_confidence_sum": pages_confidence_sum,
        }

    def _build_source(self, file_path: Path) -> Any:
        """Build a ``DocumentSource`` for *file_path* using the factory.

        Falls back to treating the file as a PDF if the sources package
        is not available (graceful degradation).
        """
        try:
            from .sources import detect_source

            return detect_source(file_path)
        except Exception:
            # Fallback for environments without the sources package
            from .sources.pdf import PdfSource

            return PdfSource(file_path)

    def _produce_document_output(
        self,
        pdf_path: Path,
        output_dir: Path,
        short_sha: str,
        page_count: int,
        source: Any = None,
    ) -> None:
        """Collect all per-page markdown and produce a concatenated document .md.

        Gathers ``page_NNNN_final.md`` files that already exist on disk (from
        this run or a previous checkpointed run), extracts metadata via
        VLM→GROBID→none fallback, and writes ``{short_sha}.md`` with YAML
        frontmatter in the output directory.
        """
        # Collect existing per-page markdown
        md_pages: list[tuple[int, str]] = []
        for i in range(page_count):
            md_path = output_dir / f"page_{i + 1:04d}_final.md"
            if md_path.is_file():
                md_text = md_path.read_text(encoding="utf-8")
                if md_text.strip():
                    md_pages.append((i, md_text))

        if not md_pages:
            return

        metadata = self._extract_metadata(pdf_path, source=source)
        if metadata or md_pages:
            # Inject per-page metadata comment when enabled
            if self.config.include_metadata_per_page and metadata:
                self._inject_page_metadata(output_dir, page_count, metadata)
            self._save_document_output(output_dir, short_sha, md_pages, metadata)

    def _inject_page_metadata(
        self,
        output_dir: Path,
        page_count: int,
        metadata: MetadataResult,
    ) -> None:
        """Prepend a metadata comment to each per-page markdown file.

        Makes every page file self-contained — readers see the document
        identity, language, and page number even without the YAML frontmatter
        from the concatenated document output.
        """
        title_part = f'" {metadata.title}"' if metadata.title else ""
        author_part = f" | author: {metadata.authors[0]}" if metadata.authors else ""
        lang_part = f" | lang: {metadata.language}" if metadata.language else ""
        doc_type = f" | type: {metadata.document_type}" if metadata.document_type else ""

        for i in range(page_count):
            md_path = output_dir / f"page_{i + 1:04d}_final.md"
            if not md_path.is_file():
                continue
            existing = md_path.read_text(encoding="utf-8")
            if existing.startswith("<!-- doc:"):
                continue  # already has metadata

            page_num = i + 1
            comment = (
                f"<!-- doc:{title_part}{author_part}{lang_part}"
                f"{doc_type} | page: {page_num} -->\n\n"
            )
            md_path.write_text(comment + existing, encoding="utf-8")

    def _extract_metadata(self, pdf_path: Path, source: Any = None) -> MetadataResult:
        """Extract metadata chain: format-native → VLM → GROBID → empty."""
        from .engines.metadata_vlm import VlmMetadataEngine

        # 0. Format-native metadata (non-PDF sources)
        if source is not None and source.source_format != "pdf":
            try:
                native = source.extract_metadata()
                if native.title or native.authors or native.source_info.format:
                    logger.info(
                        "Metadata extracted from %s source: title=%s",
                        source.source_format,
                        str(native.title)[:60],
                    )
                    return native
            except Exception as exc:
                logger.debug("Format-native metadata failed for %s: %s", source.source_format, exc)

        # 1. Try VLM first
        try:
            vlm = VlmMetadataEngine(
                vlm_model=self.config.vlm_metadata_model,
                api_key=self.config.gemini_api_key,
                page_count=3,
            )
            result = vlm.extract(pdf_path)
            if result.extraction_method == "vlm" and (result.title or result.document_type):
                logger.info(
                    "Metadata extracted via VLM: type=%s, title=%s",
                    result.document_type,
                    result.title[:60],
                )
                return result
        except Exception as exc:
            logger.warning("VLM metadata extraction failed: %s", exc)

        # 2. Fall back to GROBID
        try:
            from .engines.grobid import GrobidEngine

            engine = GrobidEngine(grobid_url=self.config.grobid_url)
            result = engine.extract_metadata(pdf_path, timeout_sec=30)
            result.extraction_method = "grobid"
            if result.title or result.doi:
                logger.info("Metadata extracted via GROBID: title=%s", result.title[:60])
                return result
        except Exception as exc:
            logger.warning("GROBID metadata extraction failed: %s", exc)

        return MetadataResult(extraction_method="none")

    def _save_document_output(
        self,
        output_dir: Path,
        short_sha: str,
        md_pages: list[tuple[int, str]],
        metadata: MetadataResult,
    ) -> None:
        """Write a per-PDF concatenated markdown file with YAML frontmatter.

        *md_pages* is a list of ``(page_index, markdown_text)`` tuples, which
        are sorted by page index before being passed to the formatter.
        """
        from .formatter import YamlFrontmatterFormatter

        pages = [
            PageResult(
                sha256="",
                page_index=i,
                page_label=f"page_{i + 1:04d}",
                merged_markdown=text,
            )
            for i, text in sorted(md_pages)
        ]
        formatter = YamlFrontmatterFormatter()
        content = formatter.format(
            metadata if metadata.extraction_method != "none" else None, pages
        )
        out_path = output_dir / f"{short_sha}.md"
        out_path.write_text(content, encoding="utf-8")
        logger.info("Saved document-level markdown for %s: %s", short_sha, out_path)

        # Also write a document.md copy for cross-PDF collection
        doc_path = output_dir / "document.md"
        doc_path.write_text(content, encoding="utf-8")

    def _produce_collection_output(self) -> None:
        """Concatenate all per-PDF document.md files into a collection.

        Finds all ``*/document.md`` under ``config.output_dir``, sorts by
        directory name, concatenates with ``\\n\\n---\\n\\n`` separators,
        and writes ``collection.md`` in the top-level output directory.
        """
        doc_files = sorted(
            self.config.output_dir.rglob("*/document.md"),
            key=lambda p: str(p.parent),
        )

        if not doc_files:
            logger.debug("No document.md files found for collection output")
            return

        parts: list[str] = []
        for doc_path in doc_files:
            text = doc_path.read_text(encoding="utf-8")
            if text.strip():
                parts.append(text)

        if not parts:
            return

        timestamp = datetime.now(timezone.utc).isoformat()
        header = (
            f"# OCR Pipeline Output\n\n"
            f"Generated: {timestamp}\n"
            f"PDFs processed: {self._pdfs_processed}\n"
            f"Total pages: {self._pages_processed}\n\n"
            f"---\n\n"
        )

        body = "\n\n---\n\n".join(parts)
        collection_path = self.config.output_dir / "collection.md"
        collection_path.write_text(header + body, encoding="utf-8")
        logger.info(
            "Saved collection output (%d document(s)): %s",
            len(doc_files),
            collection_path,
        )

    @property
    def stats(self) -> dict[str, Any]:
        """Return current processing statistics (snapshot)."""
        return self._build_stats(0.0)

    # ------------------------------------------------------------------
    # single-page processing
    # ------------------------------------------------------------------

    def _process_single_page(
        self,
        pdf_path: Path,
        page: PageResult,
        output_dir: Path,
        render_dir: Path,
        source: Any = None,
    ) -> tuple[PageResult, float]:
        """Process a single page via :class:`PageProcessor`.

        Every page independently probes for extractable text before falling
        through to the render→OCR→merge path.

        Returns:
            ``(updated_PageResult, cost)``.
        """
        processor = PageProcessor(
            config=self.config,
            budget=self.budget,
            postprocessor=self.postprocessor,
            vlm_merger=self._vlm_merger,
            engine_runner=self._run_engines_parallel,
            marker_semaphore=getattr(self, "_marker_semaphore", None),
            circuit_breakers=getattr(self, "_circuit_breakers", {}),
        )
        ctx = PageContext(
            page=page,
            pdf_path=pdf_path,
            output_dir=output_dir,
            render_dir=render_dir,
            source=source,
        )
        ctx = processor.process(ctx)
        return ctx.page, ctx.cost

    # ------------------------------------------------------------------
    # engine orchestration
    # ------------------------------------------------------------------

    def _run_engines_parallel(
        self,
        png_path: Path,
        page_index: int,
    ) -> list[EngineOutput]:
        """Run all active engines in parallel, respecting circuit breakers.

        Marker is serialized via a semaphore to prevent GPU/CPU saturation.
        """
        if not self.engines:
            logger.warning("No OCR engines available for page %d", page_index)
            return []

        active = {
            name: engine
            for name, engine in self.engines.items()
            if not self._circuit_breakers.get(name, CircuitBreaker()).is_open(name)
        }

        if not active:
            logger.warning("All engines have open circuit breakers for page %d", page_index)
            return []

        outputs: list[EngineOutput] = []
        with ThreadPoolExecutor(max_workers=min(len(active), 3)) as executor:
            future_map: dict[Future[EngineOutput], str] = {}

            for name, engine in active.items():
                if name == EngineName.MARKER:
                    future = executor.submit(
                        self._run_marker_with_semaphore,
                        engine,
                        png_path,
                        page_index,
                    )
                else:
                    future = executor.submit(
                        engine.recognize,
                        png_path,
                        page_index,
                        self.config.api_timeout_sec,
                        self.config.languages,
                    )
                future_map[future] = name

            for future in as_completed(future_map):
                name = future_map[future]
                try:
                    result = future.result()
                    outputs.append(result)

                    # Update circuit breaker
                    cb = self._circuit_breakers.get(name)
                    if cb is not None:
                        if result.error:
                            cb.record_failure(name)
                            logger.warning(
                                "Engine %s error on page %d: %s",
                                name,
                                page_index,
                                result.error,
                            )
                        else:
                            cb.record_success(name)
                except Exception as exc:
                    logger.warning("Engine %s crashed on page %d: %s", name, page_index, exc)
                    outputs.append(EngineOutput(engine=name, error=str(exc)))
                    cb = self._circuit_breakers.get(name)
                    if cb is not None:
                        cb.record_failure(name)

        return outputs

    def _run_marker_with_semaphore(
        self,
        engine: Any,
        png_path: Path,
        page_index: int,
    ) -> EngineOutput:
        """Run Marker with a semaphore to limit concurrent subprocess calls."""
        with self._marker_semaphore:
            return engine.recognize(
                png_path,
                page_index,
                self.config.api_timeout_sec,  # type: ignore[union-attr, arg-type]
                self.config.languages,
            )

    # ------------------------------------------------------------------
    # checkpoint / PDF helpers
    # ------------------------------------------------------------------

    def _compute_sha256(self, pdf_path: Path) -> str:
        """Compute SHA256 hash of a PDF file."""
        sha = hashlib.sha256()
        with open(pdf_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def _probe_extractable(self, pdf_path: Path) -> bool:
        """Probe page 0 to determine if the PDF has extractable text."""
        try:
            text, _ = extract_page_text(
                pdf_path,
                0,
                Path("/tmp"),  # temporary — we don't need the saved file
                flags=self.config.text_extraction_flags,
            )
            return bool(text.strip())
        except RenderError:
            return False

    def _get_or_create_progress(
        self,
        file_id: FileIdentity,
        pdf_path: Path,
        sha256: str,
        short_sha: str,
        rel_path: str,
        page_count: int,
    ) -> PdfProgress:
        """Get existing PdfProgress or create a new one.

        All pages start with has_extractable_text=False — each page
        probes independently during processing.
        """
        pdfs = self.checkpoint.load()

        if rel_path in pdfs:
            existing = pdfs[rel_path]
            # Update SHA256 if it changed
            if existing.file_identity and existing.file_identity.sha256 != sha256:
                existing.file_identity.sha256 = sha256
                existing.sha256 = sha256
                self.checkpoint.save(pdfs)
            return existing

        # Create new
        pages = [
            PageResult(
                sha256=sha256,
                page_index=i,
                page_label=f"page_{i + 1:04d}",
                has_extractable_text=False,
            )
            for i in range(page_count)
        ]

        pp = PdfProgress(
            sha256=sha256,
            short_sha=short_sha,
            path=rel_path,
            filename=pdf_path.name,
            page_count=page_count,
            has_extractable_text=False,
            pages=pages,
            file_identity=file_id,
        )

        pdfs[rel_path] = pp
        self.checkpoint.save(pdfs)
        return pp

    @staticmethod
    def _log_page(page: PageResult, short_sha: str) -> None:
        """Log a one-line progress summary after a page completes."""
        timings = (
            " ".join(f"{name}={eo.duration_sec:.1f}s" for name, eo in page.engine_outputs.items())
            if page.engine_outputs
            else "extracted"
        )
        logger.info(
            "Page %s of %s: %s — %s cost=$%.4f",
            page.page_label,
            short_sha,
            page.status.value,
            timings,
            page.estimated_cost,
        )

    # ------------------------------------------------------------------
    # stats
    # ------------------------------------------------------------------

    def _build_stats(self, duration_sec: float) -> dict[str, Any]:
        return {
            "pdfs_processed": self._pdfs_processed,
            "pdfs_failed": self._pdfs_failed,
            "pages_processed": self._pages_processed,
            "pages_complete": self._pages_complete,
            "pages_failed": self._pages_failed,
            "total_cost": round(self.budget.spent_usd, 4),
            "duration_sec": duration_sec,
            "avg_confidence": round(self._total_confidence / max(self._pages_complete, 1), 3),
        }
