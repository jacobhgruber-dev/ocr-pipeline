"""Language registry and discovery system for the OCR pipeline.

Provides ISO 639-1 (and some 639-2) language code mappings, engine
support sets, and validation utilities so users can discover what
languages are available without reading source code.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# ISO 639 code -> human-readable name
# ---------------------------------------------------------------------------

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "he": "Hebrew",
    "el": "Greek (modern)",
    "grc": "Greek (ancient)",
    "la": "Latin",
    "gle": "Irish (Gaeilge)",
    "gd": "Scottish Gaelic",
    "cy": "Welsh",
    "ga": "Irish (alternative code)",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "cs": "Czech",
    "sk": "Slovak",
    "hu": "Hungarian",
    "ro": "Romanian",
    "bg": "Bulgarian",
    "uk": "Ukrainian",
    "sr": "Serbian",
    "hr": "Croatian",
    "tr": "Turkish",
    "fa": "Persian",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
    "tl": "Tagalog",
    "sw": "Swahili",
    "am": "Amharic",
    "yo": "Yoruba",
    "zu": "Zulu",
    "ca": "Catalan",
    "eu": "Basque",
    "gl": "Galician",
    "oc": "Occitan",
    "eo": "Esperanto",
}

# ---------------------------------------------------------------------------
# Per-engine language support sets
# ---------------------------------------------------------------------------

# Marker uses Surya for OCR — same language set.
# Dynamic import so the list stays accurate across Surya versions.
try:
    from surya.recognition.languages import CODE_TO_LANGUAGE as _SURYA_CODES
    MARKER_LANGUAGES: set[str] = set(_SURYA_CODES.keys())
except ImportError:
    MARKER_LANGUAGES: set[str] = {
        "en", "fr", "de", "es", "it", "pt", "nl", "ru", "zh", "ja",
        "ko", "ar", "he", "sv", "no", "da", "fi", "pl", "cs", "sk",
        "hu", "ro", "bg", "uk", "tr", "fa", "hi", "th", "vi", "id",
        "ms", "ca", "el", "sr", "hr", "bn", "ta", "te", "tl", "sw",
        "am", "la", "ga",
    }

# Surya2 OCR supports 91 languages covering most scripts.
# Includes all LANGUAGE_NAMES codes plus many more.
SURYA2_LANGUAGES: set[str] = set(LANGUAGE_NAMES.keys()) | {
    "af",
    "sq",
    "hy",
    "az",
    "be",
    "bs",
    "et",
    "gu",
    "ha",
    "is",
    "jv",
    "ka",
    "kk",
    "km",
    "kn",
    "ky",
    "lo",
    "lt",
    "lv",
    "mk",
    "mn",
    "mr",
    "my",
    "ne",
    "or",
    "pa",
    "ps",
    "si",
    "sl",
    "so",
    "tg",
    "tk",
    "ug",
    "ur",
    "uz",
    "xh",
    "yi",
}

# Google Document AI supports 200+ languages.
# Includes standard ISO 639-1 codes from LANGUAGE_NAMES.
# Excludes ISO 639-2 codes (gle, grc) which Google does not
# recognise as separate language identifiers.
GOOGLE_DOC_AI_LANGUAGES: set[str] = set(LANGUAGE_NAMES.keys()) - {"gle", "grc"}

# All known engine names (for --list-engines and validation).
# Tesseract supports 100+ languages including all LANGUAGE_NAMES codes.
TESSERACT_LANGUAGES: set[str] = set(LANGUAGE_NAMES.keys())

ENGINE_NAMES: dict[str, set[str]] = {
    "marker": MARKER_LANGUAGES,
    "surya2": SURYA2_LANGUAGES,
    "google_doc_ai": GOOGLE_DOC_AI_LANGUAGES,
    "tesseract": TESSERACT_LANGUAGES,
    # mathpix does not accept explicit language hints -- it auto-detects.
    # grobid auto-detects; no per-language configuration exposed.
}
"""Mapping of engine name -> set of supported language codes."""

ENGINE_DESCRIPTIONS: dict[str, str] = {
    "marker": "Local OCR engine. Requires Python venv. Supports ~40 languages.",
    "surya2": "Local OCR engine (Surya2). Requires Python venv. Supports 91 languages.",
    "google_doc_ai": "Cloud OCR via Google Document AI API. "
    "Requires GOOGLE_APPLICATION_CREDENTIALS. Supports 200+ languages.",
    "mathpix": "Cloud OCR via Mathpix API. Requires MATHPIX_APP_ID + MATHPIX_APP_KEY. "
    "Auto-detects languages.",
    "grobid": "Metadata extraction via GROBID. Requires a running GROBID server "
    "(default http://localhost:8070).",
    "tesseract": "Local OCR engine (Tesseract). Requires tesseract binary on PATH. "
    "Supports 100+ languages.",
}
"""Human-readable descriptions for each engine."""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Languages that use right-to-left scripts
_RTL_LANGUAGES = {"ar", "fa", "ur", "he", "ps", "sd", "ug", "ku"}


def is_rtl(lang_code: str) -> bool:
    """Return True if the language code uses right-to-left script."""
    return lang_code in _RTL_LANGUAGES


def get_language_name(code: str) -> str:
    """Return the human-readable name for *code*, or *code* itself if unknown."""
    return LANGUAGE_NAMES.get(code, code)


def list_languages() -> list[str]:
    """Return a sorted list of all known language codes."""
    return sorted(LANGUAGE_NAMES.keys())


def list_languages_for_engine(engine: str) -> list[str]:
    """Return a sorted list of language codes supported by *engine*.

    ``engine`` must be one of ``"marker"``, ``"surya2"``,
    ``"google_doc_ai"``, or ``"tesseract"``.
    Raises ``ValueError`` for unknown engines.
    """
    engine_set = ENGINE_NAMES.get(engine)
    if engine_set is None:
        raise ValueError(
            f"Unknown engine: {engine!r}. Valid choices: {', '.join(sorted(ENGINE_NAMES.keys()))}"
        )
    return sorted(engine_set)


def validate_languages(
    codes: list[str],
    engine: str | None = None,
) -> tuple[list[str], list[str]]:
    """Validate a list of language codes.

    Returns ``(valid_codes, unknown_codes)``.  If *engine* is provided,
    codes that are *known* but unsupported by that engine are **not**
    treated as unknown; this function only validates that codes exist
    in :data:`LANGUAGE_NAMES`.
    """
    known = set(LANGUAGE_NAMES.keys())
    valid: list[str] = []
    unknown: list[str] = []
    for code in codes:
        if code in known:
            valid.append(code)
        else:
            unknown.append(code)

    # If an engine is specified, also warn about unsupported (but known) codes.
    if engine is not None and engine in ENGINE_NAMES:
        supported = ENGINE_NAMES[engine]
        unsupported = [c for c in valid if c not in supported]
        if unsupported:
            _warn_unsupported(engine, unsupported)

    return valid, unknown


# ---------------------------------------------------------------------------
# CLI helpers (used by cli.py)
# ---------------------------------------------------------------------------


def _engine_support_label(code: str) -> str:
    """Return a human-readable engine-support label for a language code.

    >>> _engine_support_label("en")
    "(all engines)"
    >>> _engine_support_label("gle")
    "(surya2)"
    """
    engines: list[str] = []
    if code in MARKER_LANGUAGES:
        engines.append("marker")
    if code in SURYA2_LANGUAGES:
        engines.append("surya2")
    if code in GOOGLE_DOC_AI_LANGUAGES:
        engines.append("google_doc_ai")
    if code in TESSERACT_LANGUAGES:
        engines.append("tesseract")

    if len(engines) == 4:
        return "(all engines)"
    if not engines:
        return "(none)"
    return "(" + ", ".join(engines) + ")"


def _warn_unsupported(engine: str, codes: list[str]) -> None:
    """Emit a warning for known codes that *engine* does not support."""
    import warnings

    warnings.warn(
        f"Engine {engine!r} does not support: {', '.join(sorted(codes))}. "
        "These languages will not be passed to this engine.",
        stacklevel=3,
    )


# ---------------------------------------------------------------------------
# Fuzzy correction map for common language-code mistakes
# ---------------------------------------------------------------------------

_FUZZY_CORRECTIONS: dict[str, str] = {
    "irish": "gle",
    "english": "en",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "latin": "la",
    "greek": "el",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "arabic": "ar",
    "hebrew": "he",
    "russian": "ru",
    "dutch": "nl",
    "portuguese": "pt",
    "swedish": "sv",
    "norwegian": "no",
    "danish": "da",
    "finnish": "fi",
    "polish": "pl",
    "czech": "cs",
    "hungarian": "hu",
    "romanian": "ro",
    "turkish": "tr",
    "vietnamese": "vi",
    "thai": "th",
    "hindi": "hi",
}


def warn_unknown_languages(codes: list[str]) -> list[str]:
    """Return warnings for unknown or suspicious language codes.

    Check each code against :data:`LANGUAGE_NAMES` and a fuzzy-matching
    map for common mistakes (e.g. ``"irish"`` instead of ``"gle"``).

    Args:
        codes: A list of language code strings (2-letter or 3-letter).

    Returns:
        A list of warning strings (one per unknown code).  An empty list
        means all codes are valid.
    """
    warnings: list[str] = []
    for code in codes:
        if code in LANGUAGE_NAMES:
            continue
        suggestion = _FUZZY_CORRECTIONS.get(code.lower())
        if suggestion is not None:
            name = LANGUAGE_NAMES.get(suggestion, suggestion)
            warnings.append(
                f"Unknown language code {code!r}. Did you mean {suggestion!r} ({name})?"
            )
        else:
            warnings.append(
                f"Unknown language code {code!r}. Not a recognized ISO 639 language code."
            )
    return warnings


def validate_language_config(codes: list[str]) -> None:
    """Validate a language configuration and log warnings for unknown codes.

    Calls :func:`warn_unknown_languages` and logs each warning via
    ``logging.getLogger("ocr_pipeline").warning(...)``.

    Args:
        codes: A list of language code strings to validate.
    """
    import logging

    logger = logging.getLogger("ocr_pipeline")
    for warning in warn_unknown_languages(codes):
        logger.warning(warning)
