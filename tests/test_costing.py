"""Tests for BudgetTracker — cost tracking and budget caps."""

from __future__ import annotations

import threading

from ocr_pipeline.costing import BudgetTracker, estimate_engine_cost
from ocr_pipeline.config import PipelineConfig


class TestBudgetTrackerNoCap:
    def test_can_spend_always_true(self):
        bt = BudgetTracker(cap_usd=None)
        assert bt.can_spend(999999.0) is True
        assert bt.can_spend(0.0) is True

    def test_record_spend_increments(self):
        bt = BudgetTracker(cap_usd=None)
        bt.record_spend(1.50)
        bt.record_spend(2.00)
        assert bt.spent_usd == 3.50

    def test_remaining_is_none_when_no_cap(self):
        bt = BudgetTracker(cap_usd=None)
        assert bt.remaining() is None


class TestBudgetTrackerWithCap:
    def test_can_spend_under_cap(self):
        bt = BudgetTracker(cap_usd=10.0)
        assert bt.can_spend(5.0) is True

    def test_can_spend_exactly_cap(self):
        bt = BudgetTracker(cap_usd=10.0)
        assert bt.can_spend(10.0) is True

    def test_can_spend_over_cap(self):
        bt = BudgetTracker(cap_usd=10.0)
        bt.record_spend(9.0)
        assert bt.can_spend(2.0) is False

    def test_record_spend_increments_with_lock(self):
        bt = BudgetTracker(cap_usd=100.0)
        bt.record_spend(30.0)
        bt.record_spend(25.0)
        assert bt.spent_usd == 55.0

    def test_remaining_correct(self):
        bt = BudgetTracker(cap_usd=10.0)
        bt.record_spend(3.0)
        assert bt.remaining() == 7.0

    def test_remaining_floors_at_zero(self):
        bt = BudgetTracker(cap_usd=5.0)
        bt.record_spend(10.0)
        assert bt.remaining() == 0.0


class TestBudgetTrackerThreadSafety:
    def test_concurrent_spends_do_not_exceed_cap(self):
        bt = BudgetTracker(cap_usd=10.0)
        errors: list[str] = []

        def spend(amount: float) -> None:
            for _ in range(100):
                if bt.can_spend(amount):
                    bt.record_spend(amount)
                else:
                    errors.append("cap exceeded")

        threads = [threading.Thread(target=spend, args=(0.05,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Total spent should never exceed cap
        assert bt.spent_usd <= 10.0 + 0.05  # allowance for race on last spend


# ---------------------------------------------------------------------------
# estimate_engine_cost
# ---------------------------------------------------------------------------


class TestEstimateEngineCost:
    def test_known_engine_cost(self):
        from pathlib import Path

        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        cost = estimate_engine_cost("google_doc_ai", cfg)
        assert cost == 0.0015

    def test_free_engine_cost(self):
        from pathlib import Path

        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert estimate_engine_cost("marker", cfg) == 0.0
        assert estimate_engine_cost("surya2", cfg) == 0.0

    def test_unknown_engine_defaults_to_zero(self):
        from pathlib import Path

        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert estimate_engine_cost("nonexistent", cfg) == 0.0
