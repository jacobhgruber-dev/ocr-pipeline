"""Post-processing pipeline for extracted OCR text.

Replaces the standalone ``scripts/cleanup_text_extractable.py`` with a
built-in, pluggable step pipeline.  Runs automatically after fast-path
(PyMuPDF) text extraction.

Post-processing preserves text integrity. Citation validation and
formatting is ScholiaCite's responsibility.

Usage::

    post = PostProcessor()
    cleaned = post.process(raw_text)

    # Only run specific steps:
    cleaned = post.process(raw_text, steps=["soft_hyphens", "ligature_expand"])
"""

from __future__ import annotations

import re
import unicodedata


# Characters that post-processing must NEVER damage
PRESERVED_CHARACTERS: dict[str, str] = {
    "\u00a7": "section symbol",
    "\u2013": "en dash",
    "\u2014": "em dash",
    "\u2019": "right single quote",
    "\u00b6": "pilcrow",
}


def preserved_chars_present(text: str) -> dict[str, bool]:
    """Return which preserved characters are in *text* (for debugging only)."""
    return {ch: ch in text for ch in PRESERVED_CHARACTERS}


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
