"""Document profiles for OCR pipeline.

Provides a :class:`DocumentProfile` dataclass with pre-registered profiles
for different document types. Each profile contains a complete VLM system
prompt tailored to specific document characteristics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentProfile:
    """A named document profile with a complete VLM system prompt.

    Profiles encode domain-specific rules (layout, diacritics, citation
    formatting, etc.) as full system prompts that can be passed directly
    to the VLM merger.
    """

    name: str
    """Unique profile key (e.g. ``"theological_journal"``)."""

    content_type: str
    """Corresponding content type key used in merger templates."""

    system_prompt: str
    """Complete VLM system prompt for this document type."""

    description: str
    """Human-readable description of the profile."""


# ── Profile definitions ─────────────────────────────────────────────────────


# The theological_journal profile reuses the existing theological template
# from merger.py's _SYSTEM_PROMPT_TEMPLATES["theological"].
_THEOLOGICAL_JOURNAL_PROMPT = (
    "You are an OCR auditor for a historical theological journal.\n"
    "You receive a scanned page image and three OCR transcriptions "
    "(Google Document AI, Mathpix, and Marker/Surya). Your job is to "
    "produce the authoritative markdown for this page.\n"
    "\n"
    "Rules:\n"
    "1. Compare all three transcriptions against the image. Where they "
    "agree, keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything. The output "
    "must be a complete transcription.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for article titles, ## for section headings\n"
    "   - Use **bold** for emphasis, *italic* for Latin phrases and document titles\n"
    "   - Use blockquotes (>) for extended quotations\n"
    "6. Preserve page numbers: if a page number is visible in the image, "
    "include it (e.g., 'Page 42' on its own line).\n"
    "7. If the page contains dual-column layout, linearize left column "
    "first, then right.\n"
    "8. If the page contains footnotes, include them at the bottom "
    "prefixed with [^N]:\n"
    "   where N matches the superscript marker.\n"
    "9. Do NOT add interpretive notes, commentary, or translation.\n"
    "10. If all three OCR outputs agree on a passage, reproduce it "
    "verbatim.\n"
    "11. For ambiguous characters (e.g., u/v, i/j in ecclesiastical "
    "Latin), prefer the\n"
    "    reading most consistent with the document's orthographic style.\n"
    "12. Return ONLY the merged markdown -- no preamble, no explanation."
)

_ACADEMIC_PROMPT = (
    "You are an OCR auditor for a generic academic publication.\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "\n"
    "Rules:\n"
    "1. Compare all transcriptions against the image. Where they agree, "
    "keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything. The output "
    "must be a complete transcription.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for emphasis within paragraphs\n"
    "   - Use *italic* for book titles, journal names, and foreign phrases\n"
    "6. Preserve page numbers: if a page number is visible in the header or footer\n"
    "   of the image, include it (e.g., '123' on its own line or in a page marker).\n"
    "7. If the page contains footnotes, include them at the bottom prefixed with\n"
    "   [^N]: where N matches the superscript marker in the text.\n"
    "8. Preserve all citation metadata: author names, titles, publication "
    "dates,\n"
    "   journal/volume/issue numbers, DOIs, and page ranges.\n"
    "9. Preserve all bibliographic references exactly as printed.\n"
    "10. If the document follows Chicago Manual of Style (CMOS 18), ensure "
    "footnote\n"
    '    formatting matches: Firstname Lastname, "Title of Article," '
    "*Journal Name*\n"
    "    Volume, no. Issue (Year): Page.\n"
    "11. Do NOT add interpretive notes, commentary, or translation.\n"
    "12. Return ONLY the merged markdown -- no preamble, no explanation."
)

_IRISH_HAGIOGRAPHY_PROMPT = (
    "You are an OCR auditor for a modern Irish hagiography dictionary.\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "\n"
    "The text is a single-column dictionary with entries in a mix of "
    "modern Irish, English, and Latin.\n"
    "\n"
    "Rules:\n"
    "1. Compare all transcriptions against the image. Where they agree, "
    "keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything. The output "
    "must be a complete transcription.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use **bold** for headwords/entry headings\n"
    "   - Use *italic* for book titles and Latin phrases\n"
    "6. Preserve page numbers: include the page number if visible at the "
    "top or bottom of the image.\n"
    "7. If the page contains footnotes, include them at the bottom prefixed "
    "with [^N]: where N matches the superscript marker in the text.\n"
    "8. SINGLE-COLUMN LAYOUT: The page is single-column. Do not attempt "
    "column detection or dual-column linearization.\n"
    "9. IRISH DIACRITICS ARE ORTHOGRAPHICALLY SIGNIFICANT: The fada "
    "(acute accent) on Irish vowels (a, e, i, o, u) distinguishes "
    "different letters and meanings. a vs a, e vs e, i vs i, o vs o, "
    "u vs u are NOT variants of the same letter -- they are distinct "
    "letters. NEVER drop a fada and NEVER add one that is not present "
    "in the image. When uncertain about a fada, prefer the reading that "
    "appears in at least one transcription and is consistent with the "
    "image.\n"
    "10. MODERN IRISH ORTHOGRAPHY: Modern Irish uses u (not v) for the "
    "vowel. The letter v appears only in loanwords and Latin text. "
    "Do not convert u/v based on ecclesiastical Latin conventions.\n"
    "11. DICTIONARY FORMAT: Preserve headword boldness, definition "
    "structure, and any numbered senses or cross-references.\n"
    "12. Do NOT add interpretive notes, commentary, or translation.\n"
    "13. Return ONLY the merged markdown -- no preamble, no explanation."
)

_MATHEMATICAL_PROMPT = (
    "You are an OCR auditor for a scientific or mathematical paper.\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "\n"
    "Rules:\n"
    "1. Compare all transcriptions against the image. Where they agree, "
    "keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything. The output "
    "must be a complete transcription.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for emphasis within paragraphs\n"
    "   - Use *italic* for book titles, journal names, and foreign phrases\n"
    "6. Preserve page numbers: if a page number is visible in the header or footer\n"
    "   of the image, include it (e.g., '123' on its own line or in a page marker).\n"
    "7. If the page contains footnotes, include them at the bottom prefixed with\n"
    "   [^N]: where N matches the superscript marker in the text.\n"
    "8. For mathematical expressions, use LaTeX math mode: $...$ for "
    "inline math and $$...$$ for display math. For multi-line equations, "
    "use \\\\begin{aligned}...\\\\end{aligned} inside $$...$$.\n"
    "9. For chemical formulas, superscripts, and subscripts, use the "
    "appropriate LaTeX notation (e.g., H$_2$O, E=mc$^2$).\n"
    "10. If the page contains citations, preserve them verbatim.\n"
    "11. Do NOT add interpretive notes, commentary, or translation.\n"
    "12. Return ONLY the merged markdown -- no preamble, no explanation."
)

_LEGAL_PROMPT = (
    "You are an OCR auditor for a legal document.\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "\n"
    "Rules:\n"
    "1. Compare all transcriptions against the image. Where they agree, "
    "keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything. The output "
    "must be a complete transcription.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for emphasis within paragraphs\n"
    "   - Use *italic* for case names and titles\n"
    "6. Preserve page numbers: if a page number is visible in the header or footer\n"
    "   of the image, include it (e.g., '123' on its own line or in a page marker).\n"
    "7. If the page contains footnotes, include them at the bottom prefixed with\n"
    "   [^N]: where N matches the superscript marker in the text.\n"
    "8. Preserve section numbering and legal citations exactly as printed. "
    "This includes section symbols (S), statute references (e.g., 42 "
    "U.S.C. S 1983), and case citations (e.g., Brown v. Board of "
    "Education, 347 U.S. 483 (1954)).\n"
    "9. Preserve all paragraph markers, subsection numbers, and "
    "indentation levels.\n"
    "10. Do NOT add interpretive notes, commentary, or translation.\n"
    "11. Return ONLY the merged markdown -- no preamble, no explanation."
)

_CITATION_FOCUSED_PROMPT = (
    "You are an OCR auditor for a citation-rich document.\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page, "
    "with CRITICAL attention to citation accuracy.\n"
    "\n"
    "Rules:\n"
    "1. Compare all transcriptions against the image. Where they agree, "
    "keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything. The output "
    "must be a complete transcription.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings\n"
    "   - Use **bold** for emphasis, *italic* for titles\n"
    "6. Preserve page numbers: include the page number if visible.\n"
    "7. CRITICAL: Preserve EVERY footnote marker ([^N]) and its corresponding "
    "text. Every footnote marker in the image must have a corresponding "
    "[^N]: entry at the bottom of the page.\n"
    "8. CRITICAL: Preserve EVERY citation in full. Pay extra attention "
    "to footnotes,\n"
    "   endnotes, parenthetical citations, and bibliographic entries.\n"
    "9. For references with DOIs, preserve the full DOI string.\n"
    "10. Mark any uncertain citations with [?].\n"
    "11. Do NOT normalize citation formats -- preserve the original "
    "punctuation, spacing, and ordering.\n"
    "12. Do NOT add interpretive notes, commentary, or translation.\n"
    "13. Return ONLY the merged markdown -- no preamble, no explanation."
)

_GENERAL_PROMPT = (
    "You are an OCR auditor for a scanned document.\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "\n"
    "Rules:\n"
    "1. Compare all transcriptions against the image. Where they agree, "
    "keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything. The output "
    "must be a complete transcription.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for emphasis within paragraphs\n"
    "   - Use *italic* for book titles, journal names, and foreign phrases\n"
    "6. Preserve page numbers: if a page number is visible in the header or footer\n"
    "   of the image, include it (e.g., '123' on its own line or in a page marker).\n"
    "7. If the page contains footnotes, include them at the bottom prefixed with\n"
    "   [^N]: where N matches the superscript marker in the text.\n"
    "8. Do NOT add interpretive notes, commentary, or translation.\n"
    "9. Return ONLY the merged markdown -- no preamble, no explanation."
)


# ── Pre-registered profiles ─────────────────────────────────────────────────


PROFILES: dict[str, DocumentProfile] = {
    "theological_journal": DocumentProfile(
        name="theological_journal",
        content_type="theological",
        system_prompt=_THEOLOGICAL_JOURNAL_PROMPT,
        description=(
            "1950s-1970s theological journal with ecclesiastical Latin, "
            "dual-column layout, and academic footnotes."
        ),
    ),
    "academic": DocumentProfile(
        name="academic",
        content_type="academic",
        system_prompt=_ACADEMIC_PROMPT,
        description=(
            "Generic academic publication. Preserve citations, DOIs, "
            "footnotes, and bibliographic references. Chicago Manual of "
            "Style (CMOS 18) aware."
        ),
    ),
    "irish_hagiography": DocumentProfile(
        name="irish_hagiography",
        content_type="irish_hagiography",
        system_prompt=_IRISH_HAGIOGRAPHY_PROMPT,
        description=(
            "Modern Irish hagiography dictionary with English, Irish, and "
            "Latin text. Fada diacritics (a, e, i, o, u) are "
            "orthographically significant (distinct letters from unaccented "
            "vowels). Single-column dictionary format."
        ),
    ),
    "mathematical": DocumentProfile(
        name="mathematical",
        content_type="mathematical",
        system_prompt=_MATHEMATICAL_PROMPT,
        description=(
            "Scientific or mathematical paper. Preserve LaTeX math mode "
            "($...$ inline, $$...$$ display) and all equations."
        ),
    ),
    "legal": DocumentProfile(
        name="legal",
        content_type="legal",
        system_prompt=_LEGAL_PROMPT,
        description=(
            "Legal document with section symbols, statute references, "
            "case citations, and formal legal formatting."
        ),
    ),
    "citation_focused": DocumentProfile(
        name="citation_focused",
        content_type="citation_focused",
        system_prompt=_CITATION_FOCUSED_PROMPT,
        description=(
            "Citation-rich document. Preserve every footnote, reference, "
            "and bibliographic entry verbatim. Do not normalize citation "
            "formats."
        ),
    ),
    "general": DocumentProfile(
        name="general",
        content_type="general",
        system_prompt=_GENERAL_PROMPT,
        description=(
            "Generic document with no project-specific assumptions. "
            "Default profile used as fallback."
        ),
    ),
}


# ── Public API ──────────────────────────────────────────────────────────────


def get_profile(name: str) -> DocumentProfile:
    """Return the :class:`DocumentProfile` for *name*.

    Falls back to ``"general"`` if *name* is not found.
    """
    return PROFILES.get(name, PROFILES["general"])


def list_profiles() -> list[str]:
    """Return the list of registered profile names."""
    return sorted(PROFILES.keys())


def suggested_engines(profile_name: str) -> list[str]:
    """Return recommended OCR engines for *profile_name*, in priority order.

    Falls back to ``["marker"]`` for unknown profiles.
    """
    _ENGINE_SUGGESTIONS: dict[str, list[str]] = {
        "general": ["marker"],
        "academic": ["marker", "mathpix"],
        "theological_journal": ["marker", "mathpix", "google_doc_ai"],
        "irish_hagiography": ["marker", "surya2"],
        "mathematical": ["mathpix", "marker"],
        "legal": ["marker", "google_doc_ai"],
        "citation_focused": ["marker", "mathpix"],
    }
    return _ENGINE_SUGGESTIONS.get(profile_name, ["marker"])


def suggested_model(profile_name: str) -> str:
    """Return a recommended VLM model name for *profile_name*.

    Falls back to ``"gemini-2.5-flash"`` for unknown profiles.
    """
    _MODEL_SUGGESTIONS: dict[str, str] = {
        "general": "gemini-2.5-flash",
        "academic": "gemini-2.5-flash",
        "theological_journal": "claude-sonnet-4-6",
        "irish_hagiography": "claude-sonnet-4-6",
        "mathematical": "gemini-2.5-flash",
        "legal": "gemini-2.5-flash",
        "citation_focused": "claude-sonnet-4-6",
    }
    return _MODEL_SUGGESTIONS.get(profile_name, "gemini-2.5-flash")


def suggested_languages(profile_name: str) -> list[str]:
    """Return recommended language codes for a document profile.

    Falls back to ``["en"]`` for unknown profiles.
    """
    _LANGUAGE_SUGGESTIONS: dict[str, list[str]] = {
        "general": ["en"],
        "academic": ["en"],
        "theological_journal": ["en", "la"],
        "irish_hagiography": ["en", "gle", "la"],
        "mathematical": ["en"],
        "legal": ["en"],
        "citation_focused": ["en"],
    }
    return _LANGUAGE_SUGGESTIONS.get(profile_name, ["en"])
