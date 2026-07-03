"""End-to-end integration tests for the OCR pipeline.

Prove the pipeline works against a real PDF, with both stub and real VLM
mergers.  These tests are slow and tagged ``e2e`` — run them with::

    pytest tests/test_e2e.py -v -m e2e
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.merger import StubVlmMerger
from ocr_pipeline.pipeline import Pipeline

HERE = Path(__file__).parent
FIXTURE_PDF = HERE / "fixtures" / "general" / "mixed_format.pdf"


# ---------------------------------------------------------------------------
# Test 1 — stub VLM (no API calls, safe for CI)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_pipeline_e2e_stub_vlm(tmp_path: Path) -> None:
    """Run the full pipeline against a real PDF using a stub VLM merger.

    No API calls are made — the stub returns canned text.  The test verifies
    that the pipeline does not crash, produces output files when engines
    are available, and creates the checkpoint directory.
    """
    assert FIXTURE_PDF.exists(), f"Fixture PDF missing: {FIXTURE_PDF}"

    output_dir = tmp_path / "output"
    config = PipelineConfig(
        input_dir=FIXTURE_PDF.parent,
        output_dir=output_dir,
        engines=["marker", "tesseract"],
        vlm_enabled=True,
        test_mode=True,
        profile="general",
        languages=["en"],
        render_dpi=150,
        max_workers=2,
        marker_concurrency=1,
    )

    stub = StubVlmMerger(canned_text="STUB E2E MERGED TEXT")
    pipeline = Pipeline(config, vlm_merger=stub)

    # Gracefully skip if no OCR engines could initialize (e.g. no marker
    # venv *and* no tesseract binary on PATH).
    if not pipeline.engines:
        pytest.skip("No OCR engines available — cannot run e2e test")

    result = pipeline.process_one(FIXTURE_PDF)

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    # 1. process_one returns stats with expected keys
    assert isinstance(result, dict)
    assert "pages_processed" in result
    assert "pages_complete" in result
    assert "pages_failed" in result
    assert "pages_confidence_sum" in result
    assert result["pages_processed"] >= 0

    # 2. Output *_final.md files exist somewhere under the output tree (if
    #    any pages were successfully processed).
    md_files = sorted(output_dir.rglob("*_final.md"))
    if result.get("pages_processed", 0) > 0:
        assert len(md_files) >= 1, (
            "Expected at least one *_final.md output file "
            f"but found none under {output_dir}"
        )
        # At least one markdown file should be non-empty.
        non_empty = [f for f in md_files if f.stat().st_size > 0]
        assert len(non_empty) >= 1, (
            f"All {len(md_files)} markdown output files are empty"
        )

    # 3. Checkpoint directory was created during Pipeline.__init__
    checkpoint_dir = output_dir / ".checkpoint"
    assert checkpoint_dir.exists(), (
        f"Checkpoint directory not found at {checkpoint_dir}"
    )

    # 4. StubVlmMerger was actually called (sanity check that the VLM
    #    path was exercised).
    assert stub.call_count >= 1, (
        f"StubVlmMerger.merge was never called (call_count={stub.call_count})"
    )


# ---------------------------------------------------------------------------
# Test 2 — real VLM (requires API key)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_pipeline_e2e_real_vlm(tmp_path: Path) -> None:
    """Run the pipeline against a real PDF using live Gemini or Claude API.

    Skips automatically when neither ``GEMINI_API_KEY`` nor
    ``ANTHROPIC_API_KEY`` is set in the environment.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not gemini_key and not anthropic_key:
        pytest.skip(
            "No GEMINI_API_KEY or ANTHROPIC_API_KEY in environment — "
            "skipping real VLM test"
        )

    assert FIXTURE_PDF.exists(), f"Fixture PDF missing: {FIXTURE_PDF}"

    output_dir = tmp_path / "output"
    config = PipelineConfig(
        input_dir=FIXTURE_PDF.parent,
        output_dir=output_dir,
        engines=["marker", "tesseract"],
        vlm_enabled=True,
        test_mode=True,
        profile="general",
        languages=["en"],
        render_dpi=150,
        max_workers=2,
        marker_concurrency=1,
        gemini_api_key=gemini_key,
        anthropic_api_key=anthropic_key,
    )

    pipeline = Pipeline(config)  # uses DefaultVlmMerger

    if not pipeline.engines:
        pytest.skip("No OCR engines available — cannot run real-VLM e2e test")

    result = pipeline.process_one(FIXTURE_PDF)

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    assert isinstance(result, dict)
    assert result["pages_processed"] >= 1, (
        f"Expected at least 1 page processed, got {result}"
    )

    # Output *_final.md files must exist and be non-trivial.
    md_files = sorted(output_dir.rglob("*_final.md"))
    assert len(md_files) >= 1, (
        "Expected at least one *_final.md output file, found none"
    )
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        assert len(content) > 50, (
            f"Markdown file {md_file.name} is too short ({len(content)} chars)"
        )

    # At least one output should contain recognizable English words.
    all_text = " ".join(f.read_text(encoding="utf-8") for f in md_files).lower()
    assert "the" in all_text or "and" in all_text, (
        "No recognizable English words found in merged output"
    )

    # VLM API should have been called (non-zero spend).
    assert pipeline.budget.spent_usd > 0, (
        f"VLM budget untouched (spent_usd={pipeline.budget.spent_usd}); "
        "the VLM merge was likely skipped"
    )
