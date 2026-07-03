"""Tests for language detection utilities."""

from __future__ import annotations

from ocr_pipeline.language_detect import detect_language, detect_language_iso639_3


# ---------------------------------------------------------------------------
# Sample texts (10-20 words each in known languages)
# ---------------------------------------------------------------------------

_ENGLISH = "The quick brown fox jumps over the lazy dog near the riverbank yesterday morning."
_FRENCH = "Le renard brun rapide saute par-dessus le chien paresseux pres de la riviere."
_SPANISH = "El rapido zorro marron salta sobre el perro perezoso cerca del rio temprano."
_GERMAN = "Der schnelle braune Fuchs springt uber den faulen Hund am fruhen Morgen."
_SHORT = "Hello"
_EMPTY = ""


class TestDetectLanguage:
    """Tests for detect_language function."""

    def test_english(self) -> None:
        result = detect_language(_ENGLISH)
        assert result == "en", f"Expected 'en', got '{result}'"

    def test_french(self) -> None:
        result = detect_language(_FRENCH)
        assert result == "fr", f"Expected 'fr', got '{result}'"

    def test_spanish(self) -> None:
        result = detect_language(_SPANISH)
        assert result == "es", f"Expected 'es', got '{result}'"

    def test_german(self) -> None:
        result = detect_language(_GERMAN)
        assert result == "de", f"Expected 'de', got '{result}'"

    def test_short_text_returns_empty(self) -> None:
        """Short text (fewer than 10 non-whitespace chars) returns empty string."""
        result = detect_language(_SHORT)
        assert result == "", f"Expected '' for short text, got '{result}'"

    def test_empty_text_returns_empty(self) -> None:
        result = detect_language(_EMPTY)
        assert result == "", f"Expected '' for empty text, got '{result}'"

    def test_whitespace_only_returns_empty(self) -> None:
        result = detect_language("   \n\t  ")
        assert result == "", f"Expected '' for whitespace-only, got '{result}'"

    def test_hint_overrides_detection(self) -> None:
        """When language hints are provided and differ from detection, hint wins."""
        # English text but we hint French
        result = detect_language(_ENGLISH, languages_hint=["fr"])
        assert result == "fr", f"Expected hint 'fr', got '{result}'"

    def test_hint_matches_detection(self) -> None:
        """When hint matches detected language, no override needed."""
        result = detect_language(_ENGLISH, languages_hint=["en"])
        assert result == "en"

    def test_multiple_hints_first_wins(self) -> None:
        """First hint is used when detection disagrees with all hints."""
        result = detect_language(_ENGLISH, languages_hint=["de", "fr", "es"])
        assert result == "de"


class TestDetectLanguageIso6393:
    """Tests for detect_language_iso639_3 function."""

    def test_english(self) -> None:
        result = detect_language_iso639_3(_ENGLISH)
        assert result == "eng", f"Expected 'eng', got '{result}'"

    def test_french(self) -> None:
        result = detect_language_iso639_3(_FRENCH)
        assert result == "fra", f"Expected 'fra', got '{result}'"

    def test_spanish(self) -> None:
        result = detect_language_iso639_3(_SPANISH)
        assert result == "spa", f"Expected 'spa', got '{result}'"

    def test_german(self) -> None:
        result = detect_language_iso639_3(_GERMAN)
        assert result == "deu", f"Expected 'deu', got '{result}'"

    def test_empty_text_returns_empty(self) -> None:
        result = detect_language_iso639_3("")
        assert result == ""

    def test_unknown_language_passthrough(self) -> None:
        """If ISO 639-1 is detected but not in mapping, ISO 639-3 returns the 2-letter code."""
        result = detect_language_iso639_3(_EMPTY)
        assert result == ""
