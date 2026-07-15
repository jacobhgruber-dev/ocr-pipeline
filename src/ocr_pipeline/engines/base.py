from __future__ import annotations

import functools
import logging
import os
import threading
from pathlib import Path
from typing import Protocol, runtime_checkable

import tenacity

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import EngineOutput  # used in OcrEngine Protocol type hints

# EngineName and EngineOutput live in models.py (single source of truth).

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Engine protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class OcrEngine(Protocol):
    """Protocol that all OCR engines must satisfy.

    Every engine runs recognition on a single page image and must
    be safe to call concurrently from multiple threads.
    """

    @property
    def engine_name(self) -> str:
        """Return one of EngineName constants."""
        ...

    def recognize(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float = 120.0,
        languages: list[str] | None = None,
    ) -> EngineOutput:
        """Run OCR on a single page image.  Must be thread-safe."""
        ...

    def health_check(self) -> bool:
        """Return True if the engine is available and configured."""
        ...


# ---------------------------------------------------------------------------
# Venv path helpers
# ---------------------------------------------------------------------------


def _get_venv_python(venv_path: Path) -> Path:
    """Return the python executable inside *venv_path*, handling platform differences.

    On Windows, venvs use ``Scripts/python.exe``; on Unix, ``bin/python``.
    """
    if os.name == "nt":  # Windows
        return venv_path / "Scripts" / "python.exe"
    else:
        return venv_path / "bin" / "python"


# ---------------------------------------------------------------------------
# Retry decorator (tenacity-based)
# ---------------------------------------------------------------------------


def with_api_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    extra_retry_on: tuple[type[BaseException], ...] | None = None,
):
    """Decorator factory for exponential-backoff retry on API calls.

    Usage::

        @with_api_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
        def _call_some_api(self, ...):
            ...

    The decorated function must **raise** on failure so tenacity can retry.
    The *extra_retry_on* parameter lets callers add exception types beyond
    ``requests.Timeout``, ``requests.ConnectionError``, ``OSError``, and
    ``tenacity.TryAgain`` (useful for ``subprocess.TimeoutExpired``, etc.).

    Retry statistics are attached to the wrapper as ``.retry_stats`` — a
    dict with key ``"attempts"`` (int, 0 = no retries occurred).

    The default values (3 attempts, 1 s base delay, 60 s max delay) are
    sensible for production use and match the ``PipelineConfig`` defaults.
    Engine-level retry parameters are set at decoration time rather than
    read from ``PipelineConfig`` at runtime, so changing ``max_retries``
    in config only affects VLM retries (in ``merger.py``).  If per-engine
    retry tuning becomes necessary, pass explicit kwargs to the decorator
    or refactor to instance-level configuration.
    """

    retry_conditions: tuple[type[BaseException], ...] = (
        tenacity.TryAgain,
        OSError,
    )
    # Only include requests types if requests is importable at decoration time.
    try:
        import requests  # noqa: F811
    except ImportError:
        pass
    else:
        retry_conditions = retry_conditions + (
            requests.Timeout,  # type: ignore[union-attr]
            requests.ConnectionError,  # type: ignore[union-attr]
        )
    if extra_retry_on:
        retry_conditions = retry_conditions + extra_retry_on

    stats: dict[str, int] = {"attempts": 0}

    def _before_sleep(retry_state: tenacity.RetryCallState) -> None:
        stats["attempts"] = retry_state.attempt_number

    def decorator(func):
        wrapped = tenacity.retry(
            stop=tenacity.stop_after_attempt(max_retries),
            wait=tenacity.wait_exponential(multiplier=base_delay, max=max_delay),
            retry=tenacity.retry_if_exception_type(retry_conditions),
            before_sleep=_before_sleep,
            reraise=True,
        )(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Reset per-call retry stats, then delegate to the tenacity wrapper."""
            stats["attempts"] = 0
            return wrapped(*args, **kwargs)

        wrapper.retry_stats = stats  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Tracks consecutive failures per engine.

    After *threshold* consecutive failures the breaker "opens" and
    ``is_open(engine)`` returns ``True``.  A single ``record_success``
    resets the counter and closes the breaker.  Thread-safe.
    """

    def __init__(self, threshold: int = 5) -> None:
        self._threshold = threshold
        self._failures: dict[str, int] = {}
        self._open: set[str] = set()
        self._lock = threading.Lock()

    def record_failure(self, engine: str) -> None:
        """Increment the failure counter for *engine*.

        If the counter reaches *threshold* the circuit is opened.
        """
        with self._lock:
            count = self._failures.get(engine, 0) + 1
            self._failures[engine] = count
            if count >= self._threshold:
                self._open.add(engine)

    def record_success(self, engine: str) -> None:
        """Reset the failure counter and close the circuit for *engine*."""
        with self._lock:
            self._failures[engine] = 0
            self._open.discard(engine)

    def is_open(self, engine: str) -> bool:
        """Return ``True`` if the circuit for *engine* is currently open."""
        with self._lock:
            return engine in self._open

