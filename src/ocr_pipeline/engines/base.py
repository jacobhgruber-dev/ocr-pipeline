from __future__ import annotations

import functools
import json
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

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

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


# ---------------------------------------------------------------------------
# Credential store
# ---------------------------------------------------------------------------


class CredentialStore:
    """Loads credentials from opencode config, falling back to env vars.

    Priority order:
    1. Environment variables (highest — opencode injects these for MCP servers)
    2. ``~/.config/opencode/opencode.json`` → ``credentials`` section
    3. Project ``.opencode/opencode.json`` → ``credentials`` section
    4. Legacy: ``ocr_pipeline/config.yaml`` (for non-opencode users)
    """

    _OPENDODE_GLOBAL = Path.home() / ".config" / "opencode" / "opencode.json"
    _LEGACY_CONFIG = Path(__file__).resolve().parent.parent.parent / "config.yaml"

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._load_opencode_global()
        self._load_opencode_project()
        self._load_legacy_yaml()

    # -- opencode config ---------------------------------------------------

    @staticmethod
    def _find_project_root() -> Path | None:
        """Walk up from this source file to find .opencode/opencode.json."""
        current = Path(__file__).resolve().parent
        for _ in range(12):
            candidate = current / ".opencode" / "opencode.json"
            if candidate.is_file():
                return candidate
            if current.parent == current:
                break
            current = current.parent
        return None

    def _load_opencode_global(self) -> None:
        self._load_json_credentials(self._OPENDODE_GLOBAL)

    def _load_opencode_project(self) -> None:
        proj = self._find_project_root()
        if proj:
            self._load_json_credentials(proj)

    def _load_json_credentials(self, path: Path) -> None:
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text())
        except Exception:
            return
        # 1. Top-level "credentials" section
        creds = data.get("credentials", {})
        if isinstance(creds, dict):
            for k, v in creds.items():
                if v is not None and v != "" and k not in self._data:
                    self._data[str(k)] = str(v)
        # 2. provider.*.options → map to standard key names
        providers = data.get("provider", {})
        if isinstance(providers, dict):
            provider_map = {
                "google": {"apiKey": "GEMINI_API_KEY"},
                "anthropic": {"apiKey": "ANTHROPIC_API_KEY"},
                "mathpix": {"appId": "MATHPIX_APP_ID", "appKey": "MATHPIX_APP_KEY"},
            }
            for name, field_map in provider_map.items():
                prov = providers.get(name, {})
                if isinstance(prov, dict):
                    opts = prov.get("options", {})
                    if isinstance(opts, dict):
                        for src_field, target_key in field_map.items():
                            val = opts.get(src_field, "")
                            if val and target_key not in self._data:
                                self._data[target_key] = str(val)
        # 3. MCP server env sections
        mcp = data.get("mcp", {})
        if isinstance(mcp, dict):
            for _server, cfg in mcp.items():
                if not isinstance(cfg, dict):
                    continue
                env = cfg.get("environment", cfg.get("env", {}))
                if isinstance(env, dict):
                    for k, v in env.items():
                        if v is not None and v != "" and k not in self._data:
                            self._data[str(k)] = str(v)

    # -- legacy YAML (non-opencode users) ----------------------------------

    def _load_legacy_yaml(self) -> None:
        if not self._LEGACY_CONFIG.is_file():
            return
        try:
            with open(self._LEGACY_CONFIG) as fh:
                raw = yaml.safe_load(fh)
            if isinstance(raw, dict):
                creds_section = raw.get("credentials", {})
                if isinstance(creds_section, dict):
                    for k, v in creds_section.items():
                        if v is not None and v != "" and k not in self._data:
                            self._data[str(k)] = str(v)
        except Exception:
            logger.warning(
                "Failed to parse %s",
                self._LEGACY_CONFIG,
                exc_info=True,
            )

    # -- public API --------------------------------------------------------

    def get(self, key: str) -> str | None:
        """Return the credential value for *key* or ``None``.

        Environment variables take priority over all config files.
        """
        return os.environ.get(key) or self._data.get(key)
