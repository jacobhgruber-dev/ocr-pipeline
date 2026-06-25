"""Budget tracking and cost estimation for the OCR pipeline.

Provides a thread-safe :class:`BudgetTracker` that gates VLM merge calls
when a budget cap is exceeded, and utility functions for estimating per-page
OCR engine costs.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PipelineConfig


class BudgetTracker:
    """Thread-safe cumulative cost tracker with an optional spending cap.

    Used to gate expensive API calls (VLM merges) by checking whether
    *estimated_cost* would push cumulative spending over *cap_usd*.

    Attributes:
        cap_usd: Maximum allowed spend (``None`` = unlimited).
        spent_usd: Total amount recorded so far.
    """

    def __init__(self, cap_usd: float | None = None) -> None:
        self.cap_usd = cap_usd
        self.spent_usd: float = 0.0
        self._lock = threading.Lock()

    def can_spend(self, estimated_cost: float) -> bool:
        """Return True if *estimated_cost* can be accommodated under the cap.

        If *cap_usd* is ``None`` (no budget), always returns True.
        """
        if self.cap_usd is None:
            return True
        with self._lock:
            return (self.spent_usd + estimated_cost) <= self.cap_usd

    def record_spend(self, actual_cost: float) -> None:
        """Record *actual_cost* against the running total (thread-safe)."""
        with self._lock:
            self.spent_usd += actual_cost

    def remaining(self) -> float | None:
        """Return remaining budget in USD, or None if no cap is set."""
        if self.cap_usd is None:
            return None
        return max(0.0, self.cap_usd - self.spent_usd)


def estimate_engine_cost(
    engine_name: str,
    config: "PipelineConfig",
) -> float:
    """Look up the estimated per-page cost for an OCR engine.

    Args:
        engine_name: Engine identifier (e.g. ``"google_doc_ai"``).
        config: Pipeline configuration containing
                :attr:`PipelineConfig.engine_cost_per_page`.

    Returns:
        Estimated cost in USD. Returns 0.0 if the engine is not in the
        config's cost table.
    """
    return config.engine_cost_per_page.get(engine_name, 0.0)
