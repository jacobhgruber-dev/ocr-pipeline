"""Progress tracking for long-running OCR pipeline runs.

Provides a :class:`PipelineProgress` class that wraps tqdm with
per-page cost tracking and ETA display, plus a :func:`format_duration`
helper.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from tqdm import tqdm  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from .costing import BudgetTracker

logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string.

    Examples:
        >>> format_duration(45)
        '0:00:45'
        >>> format_duration(3661)
        '1:01:01'
    """
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"


class PipelineProgress:
    """tqdm-based progress bar for OCR pipeline runs.

    Shows pages processed, elapsed/remaining time, throughput, and
    cumulative cost versus budget.

    Typical usage::

        progress = PipelineProgress(total_pages=len(pages), budget=budget)
        for i, page_result in enumerate(results):
            progress.update(i, page_result.cost)
            ...
        progress.close()
    """

    def __init__(
        self,
        total_pages: int,
        budget: BudgetTracker | None = None,
    ) -> None:
        self._budget = budget
        self._total_cost: float = 0.0
        self._start_time: float = time.monotonic()

        bar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} pages [{elapsed}<{remaining}, {rate_fmt}]"

        self._pbar = tqdm(
            total=total_pages,
            unit="page",
            bar_format=bar_format,
            dynamic_ncols=True,
        )
        self._refresh_display()

    def _build_postfix(self) -> str:
        """Return the postfix string showing cost and budget info."""
        parts = [f"cost=${self._total_cost:.4f}"]
        if self._budget is not None:
            remaining = self._budget.remaining()
            cap = self._budget.cap_usd
            if cap is not None:
                parts.append(f"budget=${remaining:.2f}/${cap:.2f}")
        return " ".join(parts)

    def _refresh_display(self) -> None:
        """Update the tqdm postfix with current cost/budget state."""
        self._pbar.set_postfix_str(self._build_postfix(), refresh=False)

    def update(self, page_index: int, cost: float = 0.0) -> None:
        """Advance the progress bar by one page and record cost.

        Args:
            page_index: The 0-based index of the page just completed
                        (unused; kept for caller symmetry).
            cost: The cost in USD for processing this page.
        """
        self._total_cost += cost
        self._pbar.update(1)
        self._refresh_display()

    def close(self) -> None:
        """Finalize and close the progress bar, logging a summary."""
        elapsed = time.monotonic() - self._start_time
        self._pbar.set_postfix_str(
            f"done  cost=${self._total_cost:.4f}  time={format_duration(elapsed)}",
            refresh=True,
        )
        self._pbar.close()
        logger.info(
            "Pipeline complete: %d pages in %s, cost $%.4f",
            self._pbar.n,
            format_duration(elapsed),
            self._total_cost,
        )
