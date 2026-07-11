from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .base import _get_venv_python, with_api_retry
from ..models import EngineName, EngineOutput


class MarkerEngine:
    """Marker/Surya local OCR engine running in a dedicated venv.

    Marker runs as a **subprocess** to avoid dependency conflicts between
    the marker/surya package set and the main project's dependencies.
    """

    def __init__(self, venv_path: Path) -> None:
        """Initialize with path to the Marker virtual environment.

        *venv_path* is required — the caller provides it from
        ``PipelineConfig.marker_venv``.
        """
        self.venv_path = Path(venv_path)
        self._python = _get_venv_python(self.venv_path)
        # Fall back to current Python if the venv executable doesn't exist
        # (e.g., marker is installed in the same venv as the pipeline)
        if not self._python.exists():
            self._python = Path(sys.executable)

    @property
    def engine_name(self) -> str:
        return EngineName.MARKER

    # -- recognise (public entry point) ---------------------------------------

    def recognize(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float = 300.0,
        languages: list[str] | None = None,
    ) -> EngineOutput:
        """Run Marker/Surya OCR on a single PNG image via subprocess.

        The heavy-lifting is delegated to ``_run_marker()`` which is
        wrapped with ``@with_api_retry`` so transient subprocess failures
        are retried with exponential backoff.
        """
        t0 = time.perf_counter()

        # --- Pre-flight checks (not retried) ---
        if not image_path.exists():
            return EngineOutput(
                engine=self.engine_name,
                error=f"Image not found: {image_path}",
            )

        if not self._python.exists():
            return EngineOutput(
                engine=self.engine_name,
                error=f"Python not found at {self._python}",
            )

        # --- Run (with retry) ---
        try:
            text = self._run_marker(image_path, timeout_sec, languages)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            retries = self._run_marker.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
            return EngineOutput(
                engine=self.engine_name,
                error=str(exc),
                duration_sec=elapsed,
                retries=retries,
            )

        elapsed = time.perf_counter() - t0
        retries = self._run_marker.retry_stats.get("attempts", 0)  # type: ignore[attr-defined]
        return EngineOutput(
            engine=self.engine_name,
            text=text,
            duration_sec=elapsed,
            retries=retries,
        )

    # -- internal (retry-wrapped) ---------------------------------------------

    @with_api_retry(extra_retry_on=(subprocess.TimeoutExpired,))
    def _run_marker(
        self, image_path: Path, timeout_sec: float, languages: list[str] | None = None
    ) -> str:
        """Core subprocess invocation — raises on failure so tenacity can retry."""

        script = f"""\
import json, sys
try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered

    converter = PdfConverter(
        artifact_dict=create_model_dict(),
    )
    rendered = converter({json.dumps(str(image_path))})
    text, ext, images = text_from_rendered(rendered)
    print(json.dumps({{"text": text}}))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
    sys.exit(1)
"""

        script_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(script)
                script_path = Path(f.name)

            result = subprocess.run(
                [str(self._python), str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env={**os.environ},
            )

            # Parse JSON output — JSONDecodeError is not retriable
            # (it means the subprocess produced malformed output, which
            # won't fix itself), so let it propagate as a plain ValueError.
            data = json.loads(result.stdout.strip())

            if "error" in data:
                raise RuntimeError(data["error"])

            text = data.get("text", "")
            if not text.strip():
                raise RuntimeError("Marker returned empty text")

            return text

        finally:
            if script_path is not None:
                try:
                    script_path.unlink()
                except OSError:
                    pass

    # -- health ---------------------------------------------------------------

    def health_check(self) -> bool:
        """Check that the venv exists and marker is importable."""
        if not self._python.exists():
            return False

        modules = ("marker.converters.pdf", "marker.models", "marker.output")

        # Same interpreter as this process → check in-process (avoids MCP
        # subprocess/env/timeout issues that produced false negatives).
        try:
            if self._python.resolve() == Path(sys.executable).resolve():
                import importlib.util

                return all(importlib.util.find_spec(m) is not None for m in modules)
        except Exception:
            pass

        check_script = (
            "import importlib.util; "
            f"mods={modules!r}; "
            "ok = all(importlib.util.find_spec(m) is not None for m in mods); "
            "print('ok' if ok else 'missing')"
        )
        try:
            result = subprocess.run(
                [str(self._python), "-c", check_script],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ},
            )
            return result.returncode == 0 and "ok" in result.stdout
        except Exception:
            return False
