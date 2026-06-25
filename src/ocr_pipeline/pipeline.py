"""Main pipeline orchestrator — ties together rendering, OCR, VLM merge, and output.

Usage::

    config = PipelineConfig(input_dir=Path("./pdfs"), output_dir=Path("./out"))
    pipeline = Pipeline(config)
    stats = pipeline.run()
    print(stats)

    # Or process a single file:
    pipeline.process_one(Path("./pdfs/document.pdf"))
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

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
    PageResult,
    PageStatus,
    PdfProgress,
)
from .page_processor import PageContext, PageProcessor
from .postprocess import PostProcessor
from .progress import PipelineProgress
from .renderer import get_page_count

logger = logging.getLogger("ocr_pipeline")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class Pipeline:
    """Multi-engine OCR pipeline with VLM merge for PDF documents.

    Processes all PDFs found in ``config.input_dir``, using a fast
    text-extraction path for pages with embedded text and a full
    render→OCR→VLM-merge path for image-only pages.
    """

    def __init__(
        self,
        config: PipelineConfig,
        vlm_merger: VlmMerger | None = None,
    ) -> None:
        self.config = config
        self._vlm_merger = vlm_merger or DefaultVlmMerger()

        # Budget
        self.budget = BudgetTracker(config.budget_cap_usd)

        # Checkpoint
        checkpoint_dir = config.checkpoint_dir or (config.output_dir / ".checkpoint")
        self.checkpoint = CheckpointManager(checkpoint_dir / "ocr_checkpoint.json")

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

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Process all PDFs in ``config.input_dir``.

        Returns:
            Stats dict with keys ``pdfs_processed``, ``pdfs_failed``,
            ``pages_processed``, ``pages_complete``, ``pages_failed``,
            ``total_cost``, ``duration_sec``.
        """
        t0 = time.perf_counter()

        pdf_paths = sorted(self.config.input_dir.rglob("*.pdf"))
        if not pdf_paths:
            logger.warning("No PDFs found in %s", self.config.input_dir)
            return self._build_stats(0.0)

        logger.info("Found %d PDF(s) in %s", len(pdf_paths), self.config.input_dir)

        progress = PipelineProgress(total_pages=len(pdf_paths), budget=self.budget)

        for i, pdf_path in enumerate(pdf_paths):
            try:
                pdf_stats = self.process_one(pdf_path)
                self._pdfs_processed += 1
                self._pages_processed += pdf_stats.get("pages_processed", 0)
                self._pages_complete += pdf_stats.get("pages_complete", 0)
                self._pages_failed += pdf_stats.get("pages_failed", 0)
            except Exception as exc:
                logger.error("Failed to process %s: %s", pdf_path.name, exc)
                self._pdfs_failed += 1
                self._pages_processed += 1  # count as attempted

            progress.update(i, 0.0)

        progress.close()

        duration = round(time.perf_counter() - t0, 1)
        return self._build_stats(duration)

    def process_one(self, pdf_path: Path) -> dict[str, Any]:
        """Process a single PDF file through the pipeline.

        Args:
            pdf_path: Absolute path to the PDF file.

        Returns:
            Per-PDF stats dict.
        """
        pdf_path = pdf_path.resolve()

        # Build file identity (without SHA256 yet — computed lazily)
        try:
            st = pdf_path.stat()
        except OSError as exc:
            raise RenderError(f"Cannot stat PDF: {pdf_path}") from exc

        rel_path = str(pdf_path.relative_to(self.config.input_dir))
        sha256 = self._compute_sha256(pdf_path)
        short_sha = sha256[:12]

        file_id = FileIdentity(
            relative_path=rel_path,
            size_bytes=st.st_size,
            mtime_epoch=st.st_mtime,
            sha256=sha256,
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
                logger.info("PDF %s: all pages already complete — skipping", short_sha)
                return {
                    "pages_processed": 0,
                    "pages_complete": 0,
                    "pages_failed": 0,
                }

        # Determine page count (per-page extractability tested individually)
        page_count = get_page_count(pdf_path)
        if self.config.test_mode:
            page_count = min(page_count, 3)

        # Get or create PdfProgress
        with self._checkpoint_lock:
            pp = self._get_or_create_progress(
                file_id=file_id,
                pdf_path=pdf_path,
                sha256=sha256,
                short_sha=short_sha,
                rel_path=rel_path,
                page_count=page_count,
            )

        # Output directory for this PDF
        output_dir = self.config.output_dir / short_sha
        render_dir = output_dir / "renders"
        output_dir.mkdir(parents=True, exist_ok=True)

        pages_processed = 0
        pages_complete = 0
        pages_failed = 0

        # Collect pages that need processing
        pending = [
            (i, pp.pages[i])
            for i in range(page_count)
            if pp.pages[i].status
            not in (PageStatus.COMPLETE, PageStatus.EXTRACTED, PageStatus.SKIPPED)
        ]

        if not pending:
            logger.info("PDF %s: all %d pages already complete", short_sha, page_count)
            return {"pages_processed": 0, "pages_complete": 0, "pages_failed": 0}

        # Process pending pages with thread pool
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_map: dict[Future[tuple[PageResult, float]], PageResult] = {}

            for page_index, page in pending:
                future = executor.submit(
                    self._process_single_page,
                    pdf_path,
                    page,
                    output_dir,
                    render_dir,
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

        return {
            "pages_processed": pages_processed,
            "pages_complete": pages_complete,
            "pages_failed": pages_failed,
        }

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
        }
