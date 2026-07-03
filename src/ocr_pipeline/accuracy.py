"""OCR accuracy metrics — CER (Character Error Rate) and WER (Word Error Rate).

Uses Levenshtein edit distance (no external dependencies required).
Reference implementations of the metrics used by ISRI, UNLV, and ABBYY
for OCR evaluation.

Usage::

    from ocr_pipeline.accuracy import cer, wer, evaluate

    ref = "The quick brown fox"
    hyp = "The qu1ck brown f0x"
    print(f"CER: {cer(ref, hyp):.1%}")   # CER: 18.2%
    print(f"WER: {wer(ref, hyp):.1%}")   # WER: 50.0%
"""

from __future__ import annotations

import re
from pathlib import Path


def _edit_distance(s1: str, s2: str) -> int:
    """Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)

    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, 1):
        curr = [i]
        for j, c2 in enumerate(s2, 1):
            curr.append(
                min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + (c1 != c2))
            )
        prev = curr

    return prev[-1]


def _word_edit_distance(w1: list[str], w2: list[str]) -> int:
    """Levenshtein edit distance between two lists of words."""
    if len(w1) < len(w2):
        return _word_edit_distance(w2, w1)

    prev = list(range(len(w2) + 1))
    for i, r1 in enumerate(w1, 1):
        curr = [i]
        for j, r2 in enumerate(w2, 1):
            curr.append(
                min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + (r1 != r2))
            )
        prev = curr

    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate.

    Returns a float between 0.0 (perfect) and 1.0+ (more edits than
    reference characters).  Normalized by reference length so that
    completely wrong output can exceed 100%.

    Lower is better.  < 1% is production-quality OCR.  < 5% is acceptable.
    """
    if not reference:
        return float("inf") if hypothesis else 0.0
    return _edit_distance(reference, hypothesis) / len(reference)


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate.

    Splits on whitespace before computing edit distance at the word level.
    Returns 0.0 for perfect, 1.0+ for poor quality.
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return float("inf") if hyp_words else 0.0
    return _word_edit_distance(ref_words, hyp_words) / len(ref_words)


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace."""
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def evaluate(
    reference_path: Path,
    hypothesis_path: Path,
    normalized: bool = True,
) -> dict[str, float]:
    """Evaluate OCR output against a ground truth reference file.

    Args:
        reference_path: Path to ground truth text file.
        hypothesis_path: Path to OCR output (e.g. page_0001_final.md).
        normalized: If True, lowercases and collapses whitespace before
                    comparison (standard practice for OCR evaluation).

    Returns:
        Dict with ``cer``, ``wer``, ``ref_chars``, ``hyp_chars``, and
        ``normalized`` keys.
    """
    ref_text = reference_path.read_text(encoding="utf-8")
    hyp_text = hypothesis_path.read_text(encoding="utf-8")

    if normalized:
        ref_text = _normalize(ref_text)
        hyp_text = _normalize(hyp_text)

    return {
        "cer": round(cer(ref_text, hyp_text), 4),
        "wer": round(wer(ref_text, hyp_text), 4),
        "ref_chars": len(ref_text),
        "hyp_chars": len(hyp_text),
        "normalized": normalized,
    }
