"""Language detection utility for OCR Pipeline documents.

Auto-detects the primary language of a text sample using ``langdetect``
(fast, lightweight, 55 languages) or ``fasttext`` (more accurate but
heavier) as an optional upgrade path.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Common OCR confusion pairs — when langdetect misidentifies similar
# languages, prefer the one specified by the user's config.
_CONFUSION_PAIRS: dict[str, str] = {
    "no": "nb",  # Norwegian Bokmål
    "bs": "hr",  # Bosnian → Croatian
    "ca": "es",  # Catalan → Spanish (context-dependent)
}


def detect_language(text: str, languages_hint: list[str] | None = None) -> str:
    """Detect the primary language of *text*.

    Args:
        text: The text sample to analyze (at least 20 chars recommended).
        languages_hint: Optional list of language codes to prefer if
            the detector is uncertain.

    Returns:
        ISO 639-1 language code (2-letter), or ``""`` if detection fails.
    """
    if not text or len(text.strip()) < 10:
        return ""

    try:
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0  # Deterministic results
        lang = detect(text)

        # Apply confusion-pair corrections
        lang = _CONFUSION_PAIRS.get(lang, lang)

        # If user specified language hints and detector disagrees, prefer hint
        if languages_hint and lang not in languages_hint:
            logger.debug(
                "Language detected as '%s' but hints are %s — preferring hint",
                lang,
                languages_hint,
            )
            return languages_hint[0]

        return lang
    except ImportError:
        # langdetect not installed
        pass
    except Exception as exc:
        logger.debug("Language detection failed: %s", exc)

    return ""


def detect_language_iso639_3(text: str) -> str:
    """Detect language and return ISO 639-3 (3-letter) code.

    This is the code format Tesseract expects for OCR.
    """
    iso2 = detect_language(text)
    if not iso2:
        return ""

    # Common ISO 639-1 → ISO 639-3 mappings
    _MAP: dict[str, str] = {
        "en": "eng", "fr": "fra", "de": "deu", "es": "spa", "it": "ita",
        "pt": "por", "nl": "nld", "ru": "rus", "zh": "chi_sim", "ja": "jpn",
        "ko": "kor", "ar": "ara", "he": "heb", "el": "ell", "la": "lat",
        "sv": "swe", "no": "nor", "da": "dan", "fi": "fin", "pl": "pol",
        "cs": "ces", "hu": "hun", "ro": "ron", "bg": "bul", "uk": "ukr",
        "tr": "tur", "hi": "hin", "th": "tha", "vi": "vie", "id": "ind",
    }
    return _MAP.get(iso2, iso2)
