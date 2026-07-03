"""Tesseract OCR engine — local, free, most widely deployed OCR engine."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

import pytesseract

from ..models import EngineName, EngineOutput

logger = logging.getLogger(__name__)


class TesseractEngine:
    """Tesseract OCR engine using pytesseract wrapper.

    Tesseract is the most widely deployed OCR engine — powers Google Books,
    is bundled with Linux distributions, and supports 100+ languages.
    Quality is lower than ML-based engines (Marker, Surya2) for general text
    but Tesseract excels at: scanned typewritten documents, structured forms,
    and as a reliable fallback when other engines fail.

    Requires the ``tesseract`` binary on PATH and ``pytesseract`` Python package.
    """

    ENGINE_NAME = EngineName.TESSERACT

    def __init__(
        self,
        tesseract_cmd: str = "tesseract",
        timeout_sec: float = 120.0,
    ) -> None:
        self._tesseract_cmd = tesseract_cmd
        self._timeout_sec = timeout_sec
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    @property
    def engine_name(self) -> str:
        return self.ENGINE_NAME

    def health_check(self) -> bool:
        """Verify the tesseract binary is callable."""
        try:
            subprocess.run(
                [self._tesseract_cmd, "--version"],
                capture_output=True,
                timeout=10,
            )
            return True
        except Exception:
            return False

    def recognize(
        self,
        image_path: Path,
        page_index: int,
        timeout_sec: float = 120.0,
        languages: list[str] | None = None,
    ) -> EngineOutput:
        """Run Tesseract OCR on a single page image.

        Args:
            image_path: Path to a PNG/JPG page image.
            page_index: 0-based page number (for logging only).
            timeout_sec: Not used by Tesseract (synchronous call).
            languages: ISO 639-3 language codes for Tesseract (e.g. ``["eng", "fra"]``).
                       Defaults to ``["eng"]`` if None.

        Returns:
            ``EngineOutput`` with ``text`` set to the recognized text.
        """
        t0 = time.perf_counter()

        if languages is None:
            languages = ["eng"]
        lang_str = "+".join(languages)

        try:
            text = pytesseract.image_to_string(
                str(image_path),
                lang=lang_str,
                config="--psm 3",  # Auto page segmentation
            )
            duration = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                text=text.strip(),
                duration_sec=duration,
            )
        except Exception as exc:
            duration = time.perf_counter() - t0
            logger.error("Tesseract failed on page %d: %s", page_index + 1, exc)
            return EngineOutput(
                engine=self.engine_name,
                text="",
                error=str(exc),
                duration_sec=duration,
            )
