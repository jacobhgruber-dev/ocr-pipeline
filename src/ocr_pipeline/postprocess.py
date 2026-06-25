"""Post-processing pipeline for extracted OCR text.

Replaces the standalone ``scripts/cleanup_text_extractable.py`` with a
built-in, pluggable step pipeline.  Runs automatically after fast-path
(PyMuPDF) text extraction.

Usage::

    post = PostProcessor()
    cleaned = post.process(raw_text)

    # Only run specific steps:
    cleaned = post.process(raw_text, steps=["soft_hyphens", "ligature_expand"])
"""

from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


class PostProcessor:
    """Applies cleanup transformations to extracted text.

    Each step is a method that takes a string and returns the cleaned
    string.  Steps are run in declaration order.
    """

    def __init__(self, steps: list[str] | None = None) -> None:
        self._step_registry = {
            "soft_hyphens": self._fix_soft_hyphens,
            "em_dash_breaks": self._fix_em_dash_breaks,
            "whitespace_normalize": self._normalize_whitespace,
            "ligature_expand": self._expand_ligatures,
            "stray_control_chars": self._strip_control_chars,
            "validate_citations": self._validate_citations,
        }
        self._enabled_steps = list(steps) if steps is not None else list(self._step_registry)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def process(self, text: str, steps: list[str] | None = None) -> str:
        """Apply enabled cleanup steps in order.  Returns cleaned text.

        Args:
            text: Raw extracted text to clean.
            steps: Override which steps to run (uses the instance default
                   if not provided).  Unknown step names are silently
                   ignored.
        """
        active = steps if steps is not None else self._enabled_steps
        result = text
        for name in active:
            func = self._step_registry.get(name)
            if func is not None:
                result = func(result)
        return result

    # ------------------------------------------------------------------
    # step implementations
    # ------------------------------------------------------------------

    def _fix_soft_hyphens(self, text: str) -> str:
        """Merge words broken by soft-hyphen + newline: ``word¬\\nnext`` → ``wordnext``.

        Removes the ``¬`` character when followed by optional whitespace
        and a newline, joining the word fragment with the next line.
        Also removes any remaining standalone ``¬`` characters.
        """
        # Soft hyphen at end of line: "word¬\nnext" → "wordnext"
        text = re.sub(r"¬\s*\n\s*", "", text)
        # Remove any remaining standalone ¬ (rare, but defensive).
        text = text.replace("¬", "")
        return text

    def _fix_em_dash_breaks(self, text: str) -> str:
        """Fix em-dashes broken across lines: ``word—\\nnext`` → ``word—next``."""
        return re.sub(r"—\s*\n\s*", "—", text)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace: collapse 3+ newlines to 2, strip trailing space."""
        # Collapse runs of 3+ blank lines into a single blank line.
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip trailing whitespace on each line.
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        return text

    def _expand_ligatures(self, text: str) -> str:
        """Expand common typographic ligatures to their decomposed forms.

        Handles fi, fl, ff, ffi, ffl, æ, and œ (both cased variants).
        Uses Unicode NFKC normalization for the standard Latin ligatures
        and explicit mapping for the less common ones.
        """
        # NFKC normalizes most Latin ligatures (ﬁ → fi, ﬂ → fl, etc.)
        text = unicodedata.normalize("NFKC", text)

        # Explicit fallback for any that survive normalization.
        _LIGATURE_MAP = {
            "\ufb00": "ff",  # ﬀ
            "\ufb01": "fi",  # ﬁ
            "\ufb02": "fl",  # ﬂ
            "\ufb03": "ffi",  # ﬃ
            "\ufb04": "ffl",  # ﬄ
            "\u00e6": "ae",  # æ
            "\u00c6": "AE",  # Æ
            "\u0153": "oe",  # œ
            "\u0152": "OE",  # Œ
        }
        for lig, expanded in _LIGATURE_MAP.items():
            text = text.replace(lig, expanded)
        return text

    def _strip_control_chars(self, text: str) -> str:
        """Remove non-printable control characters, keep all printable Unicode.

        Keeps newlines (``\\n``, 0x0A), tabs (``\\t``, 0x09), and all
        characters with code point >= 32 except DEL (0x7F).  This preserves
        accented Latin, Greek, Cyrillic, CJK, and other non-ASCII scripts
        while removing genuine control characters (0x00–0x08, 0x0B–0x0C,
        0x0E–0x1F, 0x7F).
        """
        return "".join(
            ch for ch in text if ch == "\n" or ch == "\t" or (ord(ch) >= 32 and ord(ch) != 127)
        )

    # ------------------------------------------------------------------
    # citation validation (read-only — does not modify text)
    # ------------------------------------------------------------------

    def _validate_citations(self, text: str) -> str:
        """Check for common OCR damage to citation patterns and log warnings.

        This is a lightweight, read-only validation step.  It does NOT
        modify the text — it only surfaces problems so downstream
        processes (or human reviewers) can address them.

        Checks performed:
        - Roman-numeral Pope names that may have been lowercased
        - Section symbols (§) that were corrupted
        - Denzinger abbreviations that lost their period
        - Page-range en dashes replaced by hyphens
        - AAS reference patterns that broke
        """
        _warn_roman_numeral_damage(text)
        _warn_section_symbol_absence(text)
        _warn_denzinger_damage(text)
        _warn_en_dash_damage(text)
        _warn_aas_damage(text)
        return text


# ── Citation validation helpers (module-level) ───────────────────────────


def _warn_roman_numeral_damage(text: str) -> None:
    """Log a warning if lowercased Pope numerals appear (OCR corruption sign).

    e.g. ``"Paul Vi"`` or ``"Pius Xii"`` instead of ``"PAUL VI"`` / ``"PIUS XII"``.
    """
    _DAMAGED = [
        (r"\bPaul\s+Vi\b", "PAUL VI"),
        (r"\bPius\s+Xii\b", "PIUS XII"),
        (r"\bLeo\s+Xiii\b", "LEO XIII"),
        (r"\bPius\s+Xi\b(?!II)", "PIUS XI"),  # avoid matching XI within XII
        (r"\bJohn\s+Xxiii\b", "JOHN XXIII"),
        (r"\bJohn\s+Paul\s+Ii\b", "JOHN PAUL II"),
        (r"\bBenedict\s+Xvi\b", "BENEDICT XVI"),
        (r"\bPius\s+X\b(?!III)", "PIUS X"),
    ]
    for pattern, correct in _DAMAGED:
        for match in re.finditer(pattern, text):
            logger.warning(
                "Possible OCR damage: Pope name roman numeral lowered %r "
                "(expected %r) at position %d",
                match.group(),
                correct,
                match.start(),
            )


def _warn_section_symbol_absence(text: str) -> None:
    """Log a warning if text contains canonical § patterns but no § character.

    Heuristic: if the text has ``can. N`` or ``c. N`` references and the
    § character (U+00A7) is entirely absent, the section symbol may have
    been corrupted during OCR.
    """
    if "§" in text:
        return
    # Only warn if there are canon-law-style citations that likely
    # should have § symbols.
    if re.search(r"\bcan\.\s+\d+\s+\d+", text) or re.search(r"\bc\.\s+\d+\s+\d+", text):
        logger.warning(
            "Section symbol (§) absent from text that contains canon-law "
            "style citations (e.g. 'can. 123 2').  The § may have been "
            "corrupted during OCR."
        )


def _warn_denzinger_damage(text: str) -> None:
    """Log a warning if Denzinger abbreviations are corrupted.

    e.g. ``"Denz ."`` (space before period) or lowercased ``"ds"`` / ``"dh"``.
    """
    if re.search(r"\bDenz\s+\.", text):
        logger.warning("Denzinger abbreviation appears corrupted: 'Denz .' (space before period)")
    if re.search(r"\bds\s+\d+", text):
        logger.warning("Denzinger-Schönmetzer prefix lowered: 'ds' should be 'DS'")
    if re.search(r"\bdh\s+\d+", text):
        logger.warning("Denzinger-Hünermann prefix lowered: 'dh' should be 'DH'")


def _warn_en_dash_damage(text: str) -> None:
    """Log a warning if number ranges use hyphens but no en dashes appear.

    In academic theological texts, page ranges should use en dash (U+2013).
    If the text contains many digit-digit hyphen patterns but zero en dashes,
    the en dashes may have been OCR'd as hyphens.
    """
    if "\u2013" in text:
        return
    hyphen_ranges = re.findall(r"\d+-\d+", text)
    if len(hyphen_ranges) >= 3:
        logger.warning(
            "No en dashes (–) found but %d hyphenated number ranges "
            "present (e.g. %r).  En dashes may have been OCR'd as hyphens.",
            len(hyphen_ranges),
            hyphen_ranges[:3],
        )


def _warn_aas_damage(text: str) -> None:
    """Log a warning if AAS reference patterns are broken.

    Valid: ``AAS 58 (1966) 123-145``.  Broken forms include missing parens,
    double spaces, or missing volume/year.
    """
    # Check for partial AAS patterns that don't match the canonical form
    aas_canonical = re.findall(r"AAS\s+\d+\s*\(\d{4}\)\s*\d+[-–—]\d+", text)
    aas_loose = re.findall(r"AAS\s+\d+", text)
    if aas_loose and not aas_canonical:
        logger.warning(
            "AAS references found (%d matches) but none match canonical "
            "form 'AAS VOL (YEAR) PAGE-PAGE'.  Possible OCR damage.  "
            "Examples: %r",
            len(aas_loose),
            aas_loose[:3],
        )
