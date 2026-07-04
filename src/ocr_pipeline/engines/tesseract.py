"""Tesseract OCR engine — local, free, most widely deployed OCR engine."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

import pytesseract

from ..models import Block, EngineName, EngineOutput, WordBbox

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

    # ISO 639-1 (2-letter) → ISO 639-2/T (3-letter) — Tesseract requires 3-letter codes.
    # Without this mapping, Tesseract silently falls back to English for non-English text.
    _LANG_MAP: dict[str, str] = {
        "en": "eng",
        "fr": "fra",
        "de": "deu",
        "es": "spa",
        "it": "ita",
        "pt": "por",
        "nl": "nld",
        "ru": "rus",
        "zh": "chi_sim",
        "ja": "jpn",
        "ko": "kor",
        "ar": "ara",
        "he": "heb",
        "el": "ell",
        "grc": "grc",
        "la": "lat",
        "gle": "gle",
        "gd": "gla",
        "cy": "cym",
        "sv": "swe",
        "no": "nor",
        "da": "dan",
        "fi": "fin",
        "pl": "pol",
        "cs": "ces",
        "sk": "slk",
        "hu": "hun",
        "ro": "ron",
        "bg": "bul",
        "uk": "ukr",
        "sr": "srp",
        "hr": "hrv",
        "tr": "tur",
        "fa": "fas",
        "hi": "hin",
        "bn": "ben",
        "ta": "tam",
        "te": "tel",
        "th": "tha",
        "vi": "vie",
        "id": "ind",
        "ms": "msa",
        "tl": "tgl",
        "sw": "swa",
        "am": "amh",
        "yo": "yor",
        "zu": "zul",
        "ca": "cat",
        "eu": "eus",
        "gl": "glg",
        "oc": "oci",
        "eo": "epo",
    }

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
        # Map ISO 639-1 (2-letter) codes to Tesseract's ISO 639-2/T (3-letter) codes
        mapped = [self._LANG_MAP.get(lang, lang) for lang in languages]
        lang_str = "+".join(mapped)

        try:
            text = pytesseract.image_to_string(
                str(image_path),
                lang=lang_str,
                config="--psm 3",  # Auto page segmentation
            )
            text = text.strip()

            # Extract per-word bounding box data
            data = pytesseract.image_to_data(
                str(image_path),
                lang=lang_str,
                output_type=pytesseract.Output.DICT,
            )
            word_bboxes: list[WordBbox] = []
            n_entries = len(data["text"])
            for i in range(n_entries):
                # Tesseract level 5 = word
                if data["level"][i] != 5:
                    continue
                word_text = (data["text"][i] or "").strip()
                if not word_text:
                    continue
                try:
                    left = float(data["left"][i])
                    top = float(data["top"][i])
                    width = float(data["width"][i])
                    height = float(data["height"][i])
                except (ValueError, KeyError):
                    continue
                conf_val = data["conf"][i]
                confidence = float(conf_val) / 100.0 if conf_val != "-1" else 0.0
                word_bboxes.append(
                    WordBbox(
                        text=word_text,
                        bbox=(left, top, left + width, top + height),
                        confidence=confidence,
                    )
                )

            duration = time.perf_counter() - t0
            return EngineOutput(
                engine=self.engine_name,
                text=text,
                duration_sec=duration,
                blocks=[Block(type="text", text=text, words=word_bboxes)],
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
