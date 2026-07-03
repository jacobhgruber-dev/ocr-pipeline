"""Page-level processing: extract → render → OCR → merge → save.

Extracted from ``pipeline.Pipeline._process_single_page()`` into a standalone
:class:`PageProcessor` with injectable dependencies so each phase can be
tested in isolation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import PipelineConfig
from .costing import BudgetTracker, estimate_engine_cost
from .errors import MergeError, RenderError
from .extractor import extract_page_text
from .formatter import get_formatter
from .merger import (
    VlmMerger,
    _build_system_prompt,
    compute_engine_agreement,
)
from .models import EngineName, EngineOutput, PageResult, PageStatus, now_iso
from .postprocess import PostProcessor
from .renderer import render_page

logger = logging.getLogger("ocr_pipeline")


def _detect_script(text: str) -> str:
    """Detect the dominant Unicode script from OCR output text.

    Returns one of: latin, cyrillic, cjk, arabic, greek, devanagari, other.
    """
    counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        if 0x0400 <= cp <= 0x04FF:
            counts["cyrillic"] = counts.get("cyrillic", 0) + 1
        elif 0x4E00 <= cp <= 0x9FFF:
            counts["cjk"] = counts.get("cjk", 0) + 1
        elif 0x3040 <= cp <= 0x30FF:
            counts["cjk"] = counts.get("cjk", 0) + 1  # kana
        elif 0xAC00 <= cp <= 0xD7AF:
            counts["cjk"] = counts.get("cjk", 0) + 1  # hangul
        elif 0x0600 <= cp <= 0x06FF:
            counts["arabic"] = counts.get("arabic", 0) + 1
        elif 0x0370 <= cp <= 0x03FF:
            counts["greek"] = counts.get("greek", 0) + 1
        elif 0x0900 <= cp <= 0x097F:
            counts["devanagari"] = counts.get("devanagari", 0) + 1
        elif 0x0041 <= cp <= 0x005A or 0x0061 <= cp <= 0x007A:
            counts["latin"] = counts.get("latin", 0) + 1  # A-Z, a-z
        elif 0x00C0 <= cp <= 0x024F:
            counts["latin"] = counts.get("latin", 0) + 1  # Latin Extended-A/B
        elif 0x1E00 <= cp <= 0x1EFF:
            counts["latin"] = counts.get("latin", 0) + 1  # Latin Extended Additional
        elif 0x0250 <= cp <= 0x02AF:
            counts["latin"] = counts.get("latin", 0) + 1  # IPA Extensions
        elif 0xA720 <= cp <= 0xA7FF:
            counts["latin"] = counts.get("latin", 0) + 1  # Latin Extended-D
    if not counts:
        return "latin"
    return max(counts, key=counts.get)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# PageContext
# ---------------------------------------------------------------------------


@dataclass
class PageContext:
    """Accumulates state across page processing phases.

    Each phase reads from and writes to this context.  Phases mutate the
    context in place (typically writing a handful of fields) — this keeps
    the interface simple while still making data flow explicit.
    """

    page: PageResult
    pdf_path: Path
    output_dir: Path
    render_dir: Path

    # Populated by phases
    png_path: Path | None = None
    engine_outputs: list[EngineOutput] = field(default_factory=list)
    merged_markdown: str = ""
    vlm_raw: str = ""
    vlm_model: str = ""
    agreement: float = 0.0
    cost: float = 0.0


# ---------------------------------------------------------------------------
# PageProcessor
# ---------------------------------------------------------------------------


class PageProcessor:
    """Processes a single PDF page through the OCR pipeline.

    Phases (in order, each can be tested independently):

    1. **text_extraction** — try PyMuPDF fast path
    2. **rendering** — render page to PNG
    3. **ocr** — run all active engines in parallel
    4. **merge** — decide merge strategy (skip / single / ensemble)
    5. **costing** — estimate and record costs
    6. **save** — write output files via configured formatters

    Usage::

        processor = PageProcessor(config, budget, postprocessor, vlm_merger,
                                  engine_runner)
        ctx = PageContext(page=page, pdf_path=pdf, output_dir=d, render_dir=r)
        processor.process(ctx)
    """

    def __init__(
        self,
        config: PipelineConfig,
        budget: BudgetTracker,
        postprocessor: PostProcessor,
        vlm_merger: VlmMerger,
        engine_runner,  # callable: (png_path, page_index) -> list[EngineOutput]
        marker_semaphore=None,  # threading.Semaphore for Marker concurrency
        circuit_breakers: dict[str, Any] | None = None,
    ):
        self.config = config
        self.budget = budget
        self.postprocessor = postprocessor
        self.vlm_merger = vlm_merger
        self._run_engines = engine_runner
        self._marker_semaphore = marker_semaphore
        self._circuit_breakers = circuit_breakers or {}

    # ------------------------------------------------------------------
    # main entry point
    # ------------------------------------------------------------------

    def process(self, ctx: PageContext) -> PageContext:
        """Run all phases on a page context.  Returns updated context."""
        ctx.page.started_at = now_iso()

        try:
            # Phase 1: try text extraction (fast path)
            if self._try_text_extraction(ctx):
                if not self.config.vlm_enabled:
                    return ctx
                # VLM enabled: render + merge even with embedded text
                self._render_page(ctx)
                self._vlm_merge_extracted(ctx)
                # Sync ctx.merged_markdown for _save_outputs (which uses it as source of truth)
                ctx.merged_markdown = ctx.page.merged_markdown
                self._save_outputs(ctx)
                ctx.page.status = PageStatus.COMPLETE
                ctx.page.completed_at = now_iso()
                return ctx

            # Phase 2: render to PNG
            self._render_page(ctx)

            # Capture rendered image dimensions for ALTO output
            if ctx.png_path:
                from PIL import Image
                img = Image.open(str(ctx.png_path))
                ctx.page.metadata["page_width"] = img.width
                ctx.page.metadata["page_height"] = img.height

            # Phase 3: run OCR engines
            self._run_ocr(ctx)

            if not self._has_usable_output(ctx):
                ctx.page.status = PageStatus.FAILED
                ctx.page.error = "All OCR engines failed"
                ctx.page.completed_at = now_iso()
                ctx.page.engine_outputs = {eo.engine: eo for eo in ctx.engine_outputs}
                return ctx

            # Phase 4: merge strategy
            self._merge(ctx)

            # Phase 5: estimate costs
            self._estimate_costs(ctx)

            # Compute average confidence across engine outputs
            self._compute_confidence(ctx)

            # Phase 6: save outputs
            self._save_outputs(ctx)

            ctx.page.status = PageStatus.COMPLETE
            ctx.page.completed_at = now_iso()

        except Exception as exc:
            logger.error("Page %d processing failed: %s", ctx.page.page_index, exc)
            ctx.page.status = PageStatus.FAILED
            ctx.page.error = str(exc)
            ctx.page.completed_at = now_iso()

        return ctx

    # ------------------------------------------------------------------
    # Phase 1: text extraction (fast path)
    # ------------------------------------------------------------------

    def _try_text_extraction(self, ctx: PageContext) -> bool:
        """Try PyMuPDF text extraction.  Returns True if the fast path succeeded."""
        try:
            text, _saved = extract_page_text(
                ctx.pdf_path,
                ctx.page.page_index,
                ctx.output_dir,
                flags=self.config.text_extraction_flags,
            )
            if text.strip():
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
                    content = formatter.format(ctx.page)
                    out_path = (
                        ctx.output_dir / f"{ctx.page.page_label}_final{formatter.extension()}"
                    )
                    out_path.write_text(content, encoding="utf-8")

                self._save_raw_json(ctx)
                return True
        except RenderError:
            pass
        return False

    # ------------------------------------------------------------------
    # Phase 2: rendering
    # ------------------------------------------------------------------

    def _render_page(self, ctx: PageContext) -> None:
        ctx.png_path = render_page(
            ctx.pdf_path,
            ctx.page.page_index,
            ctx.render_dir,
            dpi=self.config.render_dpi,
        )

    # ------------------------------------------------------------------
    # Phase 3: OCR engines
    # ------------------------------------------------------------------

    def _run_ocr(self, ctx: PageContext) -> None:
        ctx.engine_outputs = self._run_engines(ctx.png_path, ctx.page.page_index)

    def _has_usable_output(self, ctx: PageContext) -> bool:
        return any(eo.error is None and eo.text.strip() for eo in ctx.engine_outputs)

    # ------------------------------------------------------------------
    # Phase 4: merge strategy
    # ------------------------------------------------------------------

    def _merge(self, ctx: PageContext) -> None:
        """Decide merge strategy: skip, single-engine, or VLM ensemble."""
        usable = [eo for eo in ctx.engine_outputs if eo.error is None and eo.text.strip()]

        if not self.config.vlm_enabled:
            ctx.merged_markdown = self._pick_best(usable)
            return

        if len(usable) == 1:
            # Single engine — use output directly (no VLM needed)
            ctx.merged_markdown = usable[0].text
            return

        # Multi-engine ensemble path
        ctx.agreement = compute_engine_agreement(ctx.engine_outputs)

        if self._can_skip_vlm(ctx.engine_outputs, ctx.agreement):
            ctx.merged_markdown = self._pick_best(usable)
            return

        # Budget check before VLM call
        if not self.budget.can_spend(self.config.vlm_cost_per_call):
            logger.warning(
                "Budget exhausted (cap=$%.2f, spent=$%.4f) — skipping VLM merge for page %d",
                self.budget.cap_usd,
                self.budget.spent_usd,
                ctx.page.page_index,
            )
            ctx.merged_markdown = self._pick_best(usable)
            return

        # VLM merge
        try:
            system_prompt = _build_system_prompt(
                profile_name=self.config.profile,
                column_layout=self.config.column_layout,
                languages=self.config.languages,
                custom_prompt=self.config.vlm_system_prompt,
            )

            # Detect script and route to appropriate model
            all_text = " ".join(eo.text for eo in ctx.engine_outputs if eo.text)
            vlm_model = self._resolve_vlm_model(all_text)

            assert ctx.png_path is not None, "png_path must be set before VLM merge"
            merged_md, vlm_raw, vlm_model_used, merge_cost = self.vlm_merger.merge(
                image_path=ctx.png_path,
                engine_outputs=ctx.engine_outputs,
                page_index=ctx.page.page_index,
                pdf_identifier=ctx.page.page_label,
                system_prompt=system_prompt,
                model=vlm_model,
                fallback_model=self.config.vlm_fallback_model,
                max_tokens=self.config.vlm_max_tokens,
                timeout_sec=self.config.api_timeout_sec,
            )
            ctx.merged_markdown = merged_md
            ctx.vlm_raw = vlm_raw
            ctx.vlm_model = vlm_model_used
            self.budget.record_spend(merge_cost)
            ctx.cost += merge_cost
        except MergeError:
            logger.warning(
                "VLM merge failed for page %d — falling back to best engine",
                ctx.page.page_index,
            )
            ctx.merged_markdown = self._pick_best(usable)

    # ------------------------------------------------------------------
    # Phase 5: costing
    # ------------------------------------------------------------------

    def _estimate_costs(self, ctx: PageContext) -> None:
        engine_cost = sum(
            estimate_engine_cost(eo.engine, self.config)
            for eo in ctx.engine_outputs
            if eo.error is None and eo.text.strip()
        )
        ctx.cost += engine_cost
        ctx.page.estimated_cost = ctx.cost

    def _compute_confidence(self, ctx: PageContext) -> None:
        """Compute average confidence across all engine outputs.

        Sets ``ctx.page.confidence`` to the average of all engine
        confidence values, or ``None`` if no engine provides confidence.
        """
        confidences = [
            eo.confidence
            for eo in ctx.engine_outputs
            if eo.confidence is not None and eo.confidence > 0
        ]
        if confidences:
            ctx.page.confidence = sum(confidences) / len(confidences)
        else:
            ctx.page.confidence = None

    # ------------------------------------------------------------------
    # Phase 6: save outputs
    # ------------------------------------------------------------------

    def _save_outputs(self, ctx: PageContext) -> None:
        """Write final outputs via configured formatters."""
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        ctx.page.merged_markdown = ctx.merged_markdown
        ctx.page.engine_outputs = {eo.engine: eo for eo in ctx.engine_outputs}

        for fmt_name in self.config.output_formats:
            formatter = get_formatter(fmt_name)
            content = formatter.format(ctx.page)
            out_path = ctx.output_dir / f"{ctx.page.page_label}_final{formatter.extension()}"
            out_path.write_text(content, encoding="utf-8")

        self._save_raw_json(ctx)

    def _save_raw_json(self, ctx: PageContext) -> None:
        """Save per-page raw JSON debug artifact."""
        raw: dict[str, Any] = {
            "page_index": ctx.page.page_index,
            "page_label": ctx.page.page_label,
            "engine_outputs": {
                eo.engine: {
                    "text": eo.text,
                    "error": eo.error,
                    "duration_sec": eo.duration_sec,
                    "retries": eo.retries,
                }
                for eo in ctx.engine_outputs
            },
            "merged_markdown": ctx.merged_markdown,
            "vlm_raw_response": ctx.vlm_raw,
            "vlm_model": ctx.vlm_model,
            "engines_agreement": round(ctx.agreement, 4),
            "processed_at": ctx.page.completed_at or now_iso(),
        }
        json_path = ctx.output_dir / f"{ctx.page.page_label}_raw.json"
        json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # merge decision helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_engine_text(engine_outputs: list[EngineOutput], engine_name: str) -> str:
        """Return the text for *engine_name*, or empty string."""
        for eo in engine_outputs:
            if eo.engine == engine_name and eo.error is None:
                return eo.text
        return ""

    @classmethod
    def _pick_best(cls, usable: list[EngineOutput]) -> str:
        """Pick the best available engine output.

        Priority: Marker > Google Doc AI > Mathpix > first available.
        """
        priority = [EngineName.MARKER, EngineName.GOOGLE_DOC_AI, EngineName.MATHPIX]
        for preferred in priority:
            text = cls._get_engine_text(usable, preferred)
            if text.strip():
                return text
        # Fall through to any engine with text
        for eo in usable:
            if eo.error is None and eo.text.strip():
                return eo.text
        return ""

    def _vlm_merge_extracted(self, ctx: PageContext) -> None:
        """Send extracted text + page image through VLM for formatting."""
        from .merger import _build_system_prompt
        from .models import EngineName, EngineOutput

        if not self.budget.can_spend(self.config.vlm_cost_per_call):
            return

        # Create a pseudo engine output from the extracted text
        eo = EngineOutput(
            engine=EngineName.MARKER,
            text=ctx.page.merged_markdown,
            error=None,
        )

        try:
            system_prompt = _build_system_prompt(
                profile_name=self.config.profile,
                column_layout=self.config.column_layout,
                languages=self.config.languages,
                custom_prompt=self.config.vlm_system_prompt,
            )

            # Detect script and route to appropriate model
            vlm_model = self._resolve_vlm_model(ctx.page.merged_markdown)

            assert ctx.png_path is not None, "png_path must be set before VLM merge"
            merged_md, vlm_raw, vlm_model_used, merge_cost = self.vlm_merger.merge(
                image_path=ctx.png_path,
                engine_outputs=[eo],
                page_index=ctx.page.page_index,
                pdf_identifier=ctx.page.page_label,
                system_prompt=system_prompt,
                model=vlm_model,
                fallback_model=self.config.vlm_fallback_model,
                max_tokens=self.config.vlm_max_tokens,
                timeout_sec=self.config.api_timeout_sec,
            )
            ctx.page.merged_markdown = merged_md
            ctx.page.vlm_raw_response = vlm_raw
            ctx.page.metadata["vlm_model"] = vlm_model_used
            self.budget.record_spend(merge_cost)
            ctx.cost += merge_cost
        except Exception:
            pass  # Keep extracted text as-is

    def _resolve_vlm_model(self, all_text: str) -> str:
        """Detect script from engine text and route to the correct VLM model."""
        from .profiles import get_profile as _get_profile

        detected_script = _detect_script(all_text)
        profile = _get_profile(self.config.profile)
        vlm_model = profile.model_routing.get(detected_script, self.config.vlm_model)
        if vlm_model != self.config.vlm_model:
            logger.info(
                "Script detected: %s → routing to %s (default: %s)",
                detected_script,
                vlm_model,
                self.config.vlm_model,
            )
        return vlm_model

    def _can_skip_vlm(
        self,
        engine_outputs: list[EngineOutput],
        agreement: float,
    ) -> bool:
        """Return True if engines agree enough to skip VLM merge."""
        threshold = self.config.vlm_agreement_threshold
        if agreement < threshold:
            return False
        succeeded = [eo for eo in engine_outputs if eo.error is None and eo.text.strip()]
        return len(succeeded) >= 2
