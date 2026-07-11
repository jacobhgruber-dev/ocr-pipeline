"""Document profiles for OCR pipeline.

Provides a :class:`DocumentProfile` dataclass with pre-registered profiles
for different document types. Each profile contains a complete VLM system
prompt tailored to specific document characteristics.

User-defined profiles in ``./profiles/*.yaml`` are loaded automatically
and override or extend the built-in set.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentProfile:
    """A named document profile with a complete VLM system prompt.

    Profiles encode domain-specific rules (layout, diacritics, citation
    formatting, etc.) as full system prompts that can be passed directly
    to the VLM merger.
    """

    name: str
    """Unique profile key (e.g. ``"academic"``)."""

    system_prompt: str
    """Complete VLM system prompt for this document type."""

    description: str = ""
    """Human-readable description of the profile."""

    suggested_engines: list[str] = field(default_factory=lambda: ["marker"])
    """Recommended OCR engines for this profile, in priority order."""

    optional_engines: list[str] = field(default_factory=lambda: ["tesseract"])
    """Optional engines that provide fallback or secondary support."""

    suggested_languages: list[str] = field(default_factory=lambda: ["en"])
    """Recommended language codes for this document type."""

    model_routing: dict[str, str] = field(default_factory=dict)
    """Per-script model routing. Keys are script families (latin, cyrillic,
    cjk, arabic, greek). Values are VLM model names. Falls back to
    config.vlm_model for unmapped scripts."""

    @property
    def suggested_model(self) -> str:
        """DEPRECATED: Use model_routing instead. Returns latin model as fallback."""
        return self.model_routing.get("latin", "gemini-2.5-flash")

    @property
    def best_model(self) -> str:
        """DEPRECATED: Returns the model_routing value for latin."""
        return self.model_routing.get("latin", "gemini-2.5-flash")


# ── Profile prompt definitions ─────────────────────────────────────────────

_GENERAL_PROMPT = (
    "<role>\n"
    "You are an OCR auditor for a scanned document.\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "</role>\n"
    "\n"
    "<rules>\n"
    "1. Compare all transcriptions against the image. Where they agree, keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for strong emphasis within text\n"
    "   - Wrap book titles, journal names, and foreign phrases in *single asterisks*: "
    "*The Journal of Industrial Economics*, *de novo*, *in vitro*. "
    "The asterisks produce italic markdown formatting.\n"
    "6. Page numbers and running headers/footers:\n"
    "   - Include visible page numbers on their own line (e.g., [p. 42])\n"
    "   - Include running headers/footers prefixed with [Header: text] or [Footer: text] "
    "if they contain meaningful content (chapter titles, section names, author names, dates). "
    "This bracketed format distinguishes page headers from body text -- "
    "it prevents running headers from being confused with section headings.\n"
    "7. Tables: Format as markdown tables using | and --- separators. "
    "Preserve all column headers and row data. Mark unreadable cells with [?]. "
    "For >5 column tables, optionally use compact format.\n"
    "8. Figures, images, and illustrations:\n"
    "   - Insert placeholder: [Figure: brief description]. OCR any readable text within "
    "the graphic (diagram labels, chart annotations, component callouts, signs, captions).\n"
    "   - Include any caption after the placeholder.\n"
    "9. Footnotes: Include at bottom prefixed with [^N]: where N matches the superscript "
    "marker in the text.\n"
    "10. Multi-column layout: Linearize left column first, then right. "
    "Break at natural paragraph boundaries.\n"
    "11. Lists: Preserve bullet points and numbered lists using markdown syntax (- or 1.).\n"
    "12. Code blocks: Wrap monospaced text, code, or terminal output in ``` fences. "
    "Preserve indentation exactly.\n"
    "13. Do NOT add interpretive notes, commentary, or translation.\n"
    "</rules>\n"
    "\n"
    "<examples>\n"
    "\n"
    "--- Example page output ---\n"
    "[Header: Journal of Applied Sciences, Vol. 42, No. 3]\n"
    "[p. 247]\n"
    "\n"
    "## Introduction\n"
    "\n"
    "This paper investigates the *in vitro* degradation of polymer samples under\n"
    "controlled thermal conditions. Previous work by Smith et al. has shown that\n"
    "activation energy decreases with increased catalyst concentration.[^1]\n"
    "\n"
    "| Catalyst | Temp (C) | Rate (min^{-1}) |\n"
    "|---|---|---|\n"
    "| Fe2O3 | 200 | 0.045 |\n"
    "| TiO2 | 200 | 0.032 |\n"
    "| ZnO | 250 | 0.078 |\n"
    "\n"
    "[^1]: Smith, J. et al. *J. Polym. Sci.* 2023, 45, 112-118.\n"
    "\n"
    "</examples>\n"
    "\n"
    "<completeness>\n"
    "CRITICAL -- Completeness requirement: Do NOT stop transcribing until you have\n"
    "output EVERY word visible on the page. Your output must be a complete, unabridged\n"
    "transcription. Do not truncate, summarize, or omit any text -- this includes\n"
    "keywords, footnotes, headers, captions, and attribution lines. If text exists\n"
    "on the page, it must appear in your output. Output the COMPLETE text.\n"
    "</completeness>\n"
    "\n"
    "Return ONLY the merged markdown -- no preamble, no explanation."
)

_ACADEMIC_PROMPT = (
    "<role>\n"
    "You are an OCR auditor for an academic publication (journal article, conference paper, thesis, or scholarly monograph).\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "</role>\n"
    "\n"
    "<rules>\n"
    "1. Compare all transcriptions against the image. Where they agree, keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for emphasis within paragraphs\n"
    "   - Wrap journal names, book titles, and foreign phrases in *single asterisks*: "
    "*Journal of Applied Sciences*, *de novo*, *in vitro*. "
    "The asterisks produce italic markdown formatting.\n"
    "6. Page numbers and running headers:\n"
    "   - Include visible page numbers on their own line (e.g., [p. 247])\n"
    "   - Include journal/author names from headers prefixed with [Header: text]. "
    "This bracketed format distinguishes page headers from body text -- "
    "it prevents running headers from being confused with section headings.\n"
    "7. Structured front-matter:\n"
    "   - Abstract: Prefix with > **Abstract:** and preserve as a blockquote\n"
    "   - Keywords: Preserve as a list or comma-separated after a **Keywords:** label\n"
    "   - Author affiliations: Preserve superscript markers linking authors to affiliations\n"
    "   - Funding, data availability, and COI statements: Preserve as-is\n"
    "8. Tables: Format as markdown tables using | and --- separators. "
    "Preserve all column headers and row data exactly. Mark unreadable cells with [?]. "
    "Preserve table-specific footnotes distinctly from page-level footnotes.\n"
    "9. Figures and illustrations:\n"
    "   - Insert placeholder: [Figure N: brief description]. OCR any readable text within "
    "the graphic (diagram labels, chart annotations, component callouts, signs, captions).\n"
    "   - Include any caption after the placeholder.\n"
    "10. Footnotes: Include at bottom prefixed with [^N]: where N matches the superscript "
    "marker in the text.\n"
    "11. CRITICAL: Preserve ALL citations in full -- in-text (parenthetical, numeric, "
    "author-date), footnoted, and bibliographic entries. Do NOT normalize punctuation, "
    "spacing, or ordering. Reproduce original formatting exactly.\n"
    "12. Preserve DOIs, URLs, arXiv IDs, ISBNs, and other persistent identifiers exactly "
    "as printed. A single mistyped character makes them unresolvable.\n"
    "13. Mathematical expressions: Use LaTeX math mode -- $...$ for inline, $$...$$ for "
    "display. Preserve equation numbers. LaTeX math mode is required because the output "
    "will be rendered by MathJax. Plain text math is unreadable.\n"
    "14. Multi-column layout: Linearize left column first, then right.\n"
    "15. Do NOT add interpretive notes, commentary, or translation.\n"
    "</rules>\n"
    "\n"
    "<examples>\n"
    "\n"
    "--- Example academic page ---\n"
    "[Header: JOURNAL OF POLYMER SCIENCE, Vol. 61, No. 2]\n"
    "[p. 247]\n"
    "\n"
    "> **Abstract:** This paper investigates the *in vitro* degradation kinetics of\n"
    "> polyethylene terephthalate (PET) under controlled thermal conditions. Activation\n"
    "> energies were determined using the Arrhenius equation.\n"
    "\n"
    "**Keywords:** polymer degradation, thermal analysis, activation energy, PET, "
    "*in vitro*\n"
    "\n"
    "## 1. Introduction\n"
    "\n"
    "The degradation of PET has been extensively studied.[^1] As shown by Smith\n"
    "et al., the reaction follows first-order kinetics for $T > 200^\\circ\\text{C}$.\n"
    "\n"
    "The governing equation is:\n"
    "$$E_a = -R \\cdot \\frac{d(\\ln k)}{d(1/T)}$$\n"
    "\n"
    "| Catalyst | $T$ (C) | $k$ (min^{-1}) | $E_a$ (kJ/mol) |\n"
    "|---|---|---|---|\n"
    "| Fe2O3 | 200 | $4.5 \\times 10^{-2}$ | 85.3 \\pm 2.1 |\n"
    "| TiO2 | 200 | $3.2 \\times 10^{-2}$ | 92.7 \\pm 1.8 |\n"
    "\n"
    "[^1]: Smith, J. et al. *J. Polym. Sci.* 2023, 45, 112-118.\n"
    "\n"
    "</examples>\n"
    "\n"
    "<completeness>\n"
    "CRITICAL -- Completeness requirement: Do NOT stop transcribing until you have\n"
    "output EVERY word visible on the page. Your output must be a complete, unabridged\n"
    "transcription. Do not truncate, summarize, or omit any text -- this includes\n"
    "keywords, footnotes, headers, captions, and attribution lines. If text exists\n"
    "on the page, it must appear in your output. Output the COMPLETE text.\n"
    "</completeness>\n"
    "\n"
    "Return ONLY the merged markdown -- no preamble, no explanation."
)

_MATHEMATICAL_PROMPT = (
    "<role>\n"
    "You are an OCR auditor for a mathematical or scientific document.\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "</role>\n"
    "\n"
    "<rules>\n"
    "1. Compare all transcriptions against the image. Where they agree, keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for Theorem, Lemma, Proof, Corollary, Definition, Proposition, "
    "and Remark labels\n"
    "   - Wrap journal names, book titles, and foreign phrases in *single asterisks*. "
    "The asterisks produce italic markdown formatting.\n"
    "6. Page numbers and running headers: Include page numbers on their own line. "
    "Include running headers prefixed with [Header: text]. "
    "This bracketed format distinguishes headers from body text.\n"
    "7. CRITICAL: For ALL mathematical expressions, use LaTeX math mode:\n"
    "   - $...$ for inline math (e.g., $x \\in \\mathbb{R}$, $\\alpha + \\beta = \\gamma$)\n"
    "   - $$...$$ for display equations on their own line\n"
    "   - \\begin{aligned}...\\end{aligned} inside $$...$$ for multi-line equations\n"
    "   - \\begin{pmatrix}, \\begin{bmatrix}, or \\begin{matrix} for matrices\n"
    "   - \\begin{cases}...\\end{cases} for cases notation\n"
    "   - Preserve ALL subscripts, superscripts, and math symbols exactly\n"
    "   LaTeX math mode is REQUIRED because the output will be rendered by MathJax. "
    "Plain text math expressions are unreadable.\n"
    "8. CRITICAL: Special math script notation:\n"
    "   - Blackboard bold (double-struck) letters must use \\mathbb{}: "
    "\\mathbb{R}, \\mathbb{C}, \\mathbb{Q}, \\mathbb{Z}, \\mathbb{N}\n"
    "   - Calligraphic/script letters must use \\mathcal{}: \\mathcal{L}, \\mathcal{F}\n"
    "   - Do NOT substitute regular letters for these -- they have distinct "
    "mathematical meanings\n"
    "9. Preserve equation numbers exactly as printed: (1), (2.3), (5a), etc. "
    "Place them to the right of display equations or on their own line.\n"
    "10. Theorem/proof blocks: Preserve labels in **bold** "
    "(**Theorem 1.**, **Lemma 2.3.**, **Proof.**). "
    "Preserve end markers (QED symbols) on their own line.\n"
    "11. Code and algorithms: Preserve pseudocode and computer code in ``` fences "
    "with line numbers and indentation intact.\n"
    "12. Tables: Format as markdown tables. For numeric tables, preserve all decimal "
    "points, significant digits, and units. For statistical tables, preserve p-values, "
    "confidence intervals, and test statistics exactly.\n"
    "13. Figures: Insert [Figure: brief description]. OCR readable text within graphics. "
    "Include captions.\n"
    "14. Citations: Preserve verbatim.\n"
    "15. Do NOT add interpretive notes, commentary, or translation.\n"
    "</rules>\n"
    "\n"
    "<examples>\n"
    "\n"
    "--- Example mathematical page ---\n"
    "[Header: Advanced Calculus, 3rd Edition]\n"
    "[p. 156]\n"
    "\n"
    "**Theorem 4.2** (Mean Value Theorem). Let $f : [a,b] \\to \\mathbb{R}$ be\n"
    "continuous on $[a,b]$ and differentiable on $(a,b)$. Then there exists\n"
    "$c \\in (a,b)$ such that\n"
    "\n"
    "$$f'(c) = \\frac{f(b)-f(a)}{b-a}.$$\n"
    "\n"
    "**Proof.** Define $g(x) = f(x) - f(a) - "
    "\\frac{f(b)-f(a)}{b-a}(x-a)$. Then\n"
    "$g(a) = g(b) = 0$. By Rolle's Theorem, there exists $c \\in (a,b)$ with\n"
    "$g'(c) = 0$. Computing $g'(c)$ gives the result.\n"
    "\n"
    "**Corollary 4.3.** If $f'(x) = 0$ for all $x \\in [a,b]$, then $f$ is constant.\n"
    "\n"
    "The norm inequality follows directly:\n"
    "$$\\|f(b)-f(a)\\| \\leq \\sup_{x \\in [a,b]} \\|f'(x)\\| \\cdot |b-a|.$$\n"
    "\n"
    "</examples>\n"
    "\n"
    "<completeness>\n"
    "CRITICAL -- Completeness requirement: Do NOT stop transcribing until you have\n"
    "output EVERY word visible on the page. Your output must be a complete, unabridged\n"
    "transcription. Do not truncate, summarize, or omit any text -- this includes\n"
    "keywords, footnotes, headers, captions, and attribution lines. If text exists\n"
    "on the page, it must appear in your output. Output the COMPLETE text.\n"
    "</completeness>\n"
    "\n"
    "Return ONLY the merged markdown -- no preamble, no explanation."
)

_LEGAL_PROMPT = (
    "<role>\n"
    "You are an OCR auditor for a legal document (contract, statute, court opinion, regulation, or filing).\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "</role>\n"
    "\n"
    "<rules>\n"
    "1. Compare all transcriptions against the image. Where they agree, keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for party names, defined terms of art, and emphasized text\n"
    "   - CRITICAL: Wrap ALL case names in *single asterisks*: "
    "*Brown v. Board of Education*, *Roe v. Wade*. "
    "NEVER output a case name in plain text. The asterisks produce italic markdown "
    "required for standard legal citation (Bluebook Rule 2.1).\n"
    "6. Page numbers and jurisdictional headers: Include page numbers, docket numbers, "
    "case numbers, and jurisdictional headers on their own line. Include running headers "
    "prefixed with [Header: text]. This bracketed format distinguishes page headers from "
    "body text.\n"
    "7. CRITICAL: Preserve legal citations EXACTLY:\n"
    "   - Section symbols: Section and double-section -- never substitute for them\n"
    "   - Statute references: 42 U.S.C. 1983, 26 U.S.C. 501(c)(3)\n"
    "   - Case citations: *Party v. Party*, Volume Reporter Page (Year)\n"
    "   - Regulation references: 26 C.F.R. 1.61-1, Fed. R. Civ. P. 12(b)(6)\n"
    "   - A single wrong character in a citation makes it useless for legal research\n"
    "8. Paragraph hierarchy: Preserve numbered paragraphs and sub-paragraphs: "
    "(a), (1), (i), (A). Use indentation to reflect hierarchy -- "
    "it carries legal meaning.\n"
    "9. Signature blocks: Preserve as structured text: [Signature], [Date], [Title]. "
    "Preserve printed names, dates, titles, and notary commission information. "
    "Mark handwritten signatures as [Signature].\n"
    "10. Tables: Format as markdown tables. Preserve all headers and row data. "
    "Mark unreadable cells with [?].\n"
    "11. Footnotes: Include at bottom prefixed with [^N]: where N matches the marker "
    "in the text.\n"
    "12. Defined terms: Preserve words/phrases in quotes or bold that carry special "
    "legal meaning. Reproduce exactly as formatted.\n"
    "13. Marginal notes and amendment markers: Include at point they appear, "
    "prefixed with [Margin: ...]. Mark unreadable marginalia with [Margin: illegible].\n"
    "14. Figures: Insert [Figure: brief description]. OCR readable text within graphics. "
    "Include captions.\n"
    "15. Do NOT add interpretive notes, commentary, or translation.\n"
    "</rules>\n"
    "\n"
    "<examples>\n"
    "\n"
    "--- Example legal page ---\n"
    "[Header: 347 U.S. 483]\n"
    "[Header: BROWN v. BOARD OF EDUCATION]\n"
    "\n"
    "## Opinion of the Court\n"
    "\n"
    "MR. CHIEF JUSTICE WARREN delivered the opinion of the Court.\n"
    "\n"
    "These cases come to us from the States of Kansas, South Carolina, Virginia,\n"
    "and Delaware. They are premised on different facts and different local conditions,\n"
    "but a common legal question justifies their consideration together in this\n"
    "consolidated opinion.\n"
    "\n"
    "In each of the cases, minors of the Negro race, through their legal\n"
    "representatives, seek the aid of the courts in obtaining admission to the public\n"
    "schools of their community on a nonsegregated basis. In each instance, they had\n"
    "been denied admission to schools attended by white children under laws requiring\n"
    "or permitting segregation according to race. This segregation was alleged to\n"
    "deprive the plaintiffs of the equal protection of the laws under the Fourteenth\n"
    "Amendment. In each of the cases except the Delaware case, a three-judge federal\n"
    'district court denied relief to the plaintiffs on the so-called "separate but\n'
    'equal" doctrine announced by this Court in *Plessy v. Ferguson*, 163 U.S. 537.\n'
    "\n"
    "[^1]: See *Sweatt v. Painter*, 339 U.S. 629 (1950).\n"
    "\n"
    "</examples>\n"
    "\n"
    "<completeness>\n"
    "CRITICAL -- Completeness requirement: Do NOT stop transcribing until you have\n"
    "output EVERY word visible on the page. Your output must be a complete, unabridged\n"
    "transcription. Do not truncate, summarize, or omit any text -- this includes\n"
    "keywords, footnotes, headers, captions, and attribution lines. If text exists\n"
    "on the page, it must appear in your output. Output the COMPLETE text.\n"
    "</completeness>\n"
    "\n"
    "Return ONLY the merged markdown -- no preamble, no explanation."
)

_TECHNICAL_PROMPT = (
    "<role>\n"
    "You are an OCR auditor for a technical or engineering document (specification, manual, datasheet, or API reference).\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "</role>\n"
    "\n"
    "<rules>\n"
    "1. Compare all transcriptions against the image. Where they agree, keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for document titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for callout labels: **WARNING**, **CAUTION**, **NOTE**, "
    "**IMPORTANT**, **TIP**\n"
    "   - Wrap document titles and references in *single asterisks*. "
    "The asterisks produce italic markdown formatting.\n"
    "6. Page numbers and document identifiers: Include page numbers, revision numbers, "
    "document part numbers, and version strings on their own line. Include running "
    "headers prefixed with [Header: text]. This bracketed format distinguishes headers "
    "from body text -- it prevents running headers from being confused with section "
    "headings.\n"
    "7. Callout boxes: Place the **bold** label on its own line, then indent or "
    "blockquote the callout body to distinguish it from surrounding text.\n"
    "8. Tables: Format as markdown tables. Preserve headers, row data, and units. "
    "Mark unreadable cells with [?]. For revision tables, preserve revision numbers, "
    "dates, authors, and change descriptions. For Bills of Materials, preserve part "
    "numbers, quantities, and descriptions exactly.\n"
    "9. CRITICAL: Preserve technical values exactly as printed:\n"
    "   - Tolerances and units: preserve all tolerance values and units exactly\n"
    "   - Part numbers and version strings: do NOT correct apparent typos\n"
    "   - A single wrong digit in a part number or tolerance makes the document "
    "unreliable for engineering use\n"
    "10. Code and commands: Wrap in ``` fences. Add language hint if recognizable "
    "(python, json, yaml, bash, sql). Preserve indentation, prompts ($, #, >), "
    "and special characters exactly.\n"
    "11. Diagrams, schematics, and flowcharts: Insert [Diagram: brief description]. "
    "OCR readable text within graphics (labels, callouts, annotations). Include figure "
    "numbers and captions. Do NOT recreate as ASCII art.\n"
    "12. Procedure steps: Preserve numbering using numbered lists (1. 2. 3.) "
    "with substeps preserved.\n"
    "13. Figures and photographs: Insert [Figure: brief description]. Include captions.\n"
    "14. Do NOT add interpretive notes, commentary, or translation.\n"
    "</rules>\n"
    "\n"
    "<examples>\n"
    "\n"
    "--- Example technical page ---\n"
    "[Header: ACME Valve Assembly - Installation Manual, Rev 3.2]\n"
    "[p. 15]\n"
    "\n"
    "## 4.2 Torque Specifications\n"
    "\n"
    "**WARNING:** Failure to observe torque specifications may result in\n"
    "catastrophic seal failure. Always use a calibrated torque wrench.\n"
    "\n"
    "| Bolt Size | Torque (N.m) | Tolerance |\n"
    "|---|---|---|\n"
    "| M6 | 9.5 | +/-0.5 |\n"
    "| M8 | 23.0 | +/-1.0 |\n"
    "| M10 | 46.0 | +/-2.0 |\n"
    "\n"
    "**NOTE:** Apply Loctite 242 to all stainless steel fasteners.\n"
    "\n"
    "To verify installation:\n"
    "```bash\n"
    "$ torque-verify --spec=acme-v3 --port=/dev/ttyUSB0\n"
    "PASS: All bolts within tolerance (+/-2.0%)\n"
    "```\n"
    "\n"
    "[Diagram: Exploded view of valve assembly showing parts A-1047 through A-1052]\n"
    "Fig. 3: Valve Body Assembly, Exploded View\n"
    "\n"
    "</examples>\n"
    "\n"
    "<completeness>\n"
    "CRITICAL -- Completeness requirement: Do NOT stop transcribing until you have\n"
    "output EVERY word visible on the page. Your output must be a complete, unabridged\n"
    "transcription. Do not truncate, summarize, or omit any text -- this includes\n"
    "keywords, footnotes, headers, captions, and attribution lines. If text exists\n"
    "on the page, it must appear in your output. Output the COMPLETE text.\n"
    "</completeness>\n"
    "\n"
    "Return ONLY the merged markdown -- no preamble, no explanation."
)

_BOOKS_PROMPT = (
    "<role>\n"
    "You are an OCR auditor for a book page (monograph, fiction, textbook, or reference work).\n"
    "You receive a scanned page image and multiple OCR transcriptions.\n"
    "Your job is to produce the authoritative markdown for this page.\n"
    "</role>\n"
    "\n"
    "<rules>\n"
    "1. Compare all transcriptions against the image. Where they agree, keep the consensus.\n"
    "2. Where they disagree, use the image to determine the correct text.\n"
    "3. Preserve ALL text -- do not summarize or omit anything.\n"
    "4. Mark any text you cannot read with [illegible].\n"
    "5. Format as clean markdown:\n"
    "   - Use # for chapter titles, ## for section headings, ### for subsections\n"
    "   - Use **bold** for emphasis within text\n"
    "   - Wrap book titles mentioned in the text, foreign phrases, and epigraphs "
    "in *single asterisks*. The asterisks produce italic markdown formatting.\n"
    "6. Page numbers: Include visible page numbers on their own line. "
    "Front matter often uses Roman numerals (i, ii, iii) -- "
    "preserve the original numbering exactly.\n"
    "7. Running headers: Include chapter titles, section names, or author names from "
    "headers prefixed with [Header: text]. This bracketed format distinguishes page "
    "headers from body text -- it prevents running headers from being confused with "
    "section headings.\n"
    "8. Front and back matter:\n"
    "   - Table of contents: Preserve chapter titles and page references with indentation\n"
    "   - Index entries: Preserve terms and page references in alphabetical order\n"
    "   - Glossary: Preserve terms in **bold** followed by definitions\n"
    "   - Bibliography: Preserve entries exactly, with hanging indents if present\n"
    "9. Block quotes and epigraphs: Use > for block quotes. Epigraphs at chapter "
    "openings should be italicized with the quote on one line and the attribution "
    "on the next line prefixed with >.\n"
    "10. Dialogue (fiction): Preserve paragraph breaks for each speaker change. "
    "Preserve quotation marks exactly as printed.\n"
    "11. Scene breaks: Mark with * * * on its own line.\n"
    "12. Illustrations, figures, and plates: Insert [Illustration: brief description]. "
    "OCR readable text within graphics. Include captions, credit lines, and figure "
    "numbers.\n"
    "13. Footnotes and endnotes: Include at bottom prefixed with [^N]: where N matches "
    "the marker in the text.\n"
    "14. Sidebars, callouts, and exercises (textbooks): Preserve content labeled with "
    "[Sidebar: title] or [Exercise N.]. Preserve instructions, questions, and answer "
    "keys exactly.\n"
    "15. Cross-references: Preserve references exactly.\n"
    "16. Multi-column layout: Linearize left column first, then right.\n"
    "17. Do NOT add interpretive notes, commentary, or translation.\n"
    "</rules>\n"
    "\n"
    "<examples>\n"
    "\n"
    "--- Example book page with epigraph and attribution ---\n"
    "[Header: PART I -- THE BEGINNING]\n"
    "\n"
    '> "Light is the shadow of God."\n'
    "> --Plato\n"
    "\n"
    '> "All men by nature desire to know."\n'
    "> --Aristotle, *Metaphysics*\n"
    "\n"
    "* * *\n"
    "\n"
    "# Chapter 1\n"
    "\n"
    "The afternoon sun cast long shadows across the courtyard as Elena\n"
    "made her way toward the library. She had spent the morning poring\n"
    "over the manuscripts, each one more cryptic than the last.\n"
    "\n"
    '"Have you found anything?" Marco asked, falling into step beside her.\n'
    "\n"
    '"Nothing conclusive," she said. "But there is a pattern in the\n'
    'marginalia that I cannot ignore."\n'
    "\n"
    "[^1]: The Codex Aurelius, folio 47v, contains a similar marginal notation.\n"
    "\n"
    "</examples>\n"
    "\n"
    "<completeness>\n"
    "CRITICAL -- Completeness requirement: Do NOT stop transcribing until you have\n"
    "output EVERY word visible on the page. Your output must be a complete, unabridged\n"
    "transcription. Do not truncate, summarize, or omit any text -- this includes\n"
    "keywords, footnotes, headers, captions, and attribution lines. If text exists\n"
    "on the page, it must appear in your output. Output the COMPLETE text.\n"
    "</completeness>\n"
    "\n"
    "<attribution>\n"
    "CRITICAL -- Attribution preservation: Preserve ALL attribution and credit lines.\n"
    'Epigraph attributions, quote attributions ("--Plato", "--Aristotle"), chapter\n'
    "epigraph sources, illustration credits, and footnotes must be transcribed in full.\n"
    "Attribution text is content, not decoration. Every visible character matters.\n"
    "</attribution>\n"
    "\n"
    "Return ONLY the merged markdown -- no preamble, no explanation."
)


# ── Pre-registered profiles ─────────────────────────────────────────────────

PROFILES: dict[str, DocumentProfile] = {
    "general": DocumentProfile(
        name="general",
        system_prompt=_GENERAL_PROMPT,
        description=(
            "Generic document. Catch-all with 15 rules covering tables, figures, "
            "multi-column, headers/footers, lists, and code blocks. Supports all "
            "30 input formats. Add surya2 for layout analysis + ML table detection. "
            "Uses Grok-4.3 for CJK script documents."
        ),
        suggested_engines=["marker", "tesseract"],
        optional_engines=["surya2", "mathpix", "google_doc_ai", "trocr"],
        suggested_languages=["en"],
        model_routing={
            "latin": "gemini-2.5-flash",
            "cyrillic": "gemini-2.5-flash",
            "cjk": "grok-4.3",
            "arabic": "gemini-2.5-flash",
            "greek": "gemini-2.5-flash",
        },
    ),
    "academic": DocumentProfile(
        name="academic",
        system_prompt=_ACADEMIC_PROMPT,
        description=(
            "Academic publication. Preserves citations (all styles), DOIs, abstracts, "
            "author affiliations, footnotes, tables with notes, and equations. "
            "Add surya2 for layout analysis of multi-column papers. Add grobid "
            "for structured metadata extraction."
        ),
        suggested_engines=["marker", "mathpix"],
        optional_engines=["surya2", "tesseract", "grobid"],
        suggested_languages=["en"],
        model_routing={
            "latin": "gemini-2.5-flash",
            "cyrillic": "gemini-2.5-flash",
            "cjk": "grok-4.3",
            "arabic": "gemini-2.5-flash",
            "greek": "gemini-2.5-flash",
        },
    ),
    "mathematical": DocumentProfile(
        name="mathematical",
        system_prompt=_MATHEMATICAL_PROMPT,
        description=(
            "Mathematical or scientific document. Preserves LaTeX math mode, "
            "blackboard bold, calligraphic letters, theorem/proof blocks, "
            "and equation numbers. Grok-4.3 recommended for best LaTeX equation "
            "formatting. Surya2 optional for layout + tables."
        ),
        suggested_engines=["mathpix", "marker", "tesseract"],
        optional_engines=["surya2"],
        suggested_languages=["en"],
        model_routing={
            "latin": "grok-4.3",
            "cyrillic": "grok-4.3",
            "cjk": "grok-4.3",
            "arabic": "gemini-2.5-flash",
            "greek": "gemini-2.5-flash",
        },
    ),
    "legal": DocumentProfile(
        name="legal",
        system_prompt=_LEGAL_PROMPT,
        description=(
            "Legal document. Preserves section symbols, case citations, "
            "paragraph hierarchy, signature blocks, and marginalia. "
            "Add google_doc_ai for forms and structured layouts. "
            "Add trocr for handwritten signatures and annotations."
        ),
        suggested_engines=["marker", "mathpix", "google_doc_ai"],
        optional_engines=["surya2", "tesseract", "google_doc_ai", "trocr"],
        suggested_languages=["en"],
        model_routing={
            "latin": "gemini-2.5-flash",
            "cyrillic": "gemini-2.5-flash",
            "cjk": "grok-4.3",
            "arabic": "gemini-2.5-flash",
            "greek": "gemini-2.5-flash",
        },
    ),
    "technical": DocumentProfile(
        name="technical",
        system_prompt=_TECHNICAL_PROMPT,
        description=(
            "Technical or engineering document. Preserves callout boxes, revision "
            "tables, tolerances, part numbers, code blocks with syntax hints, "
            "diagrams, and procedure steps. Add google_doc_ai for structured "
            "datasheets, complex spec tables. Grok-4.3 recommended for detailed "
            "figure and table extraction."
        ),
        suggested_engines=["marker", "mathpix", "google_doc_ai"],
        optional_engines=["surya2", "tesseract", "google_doc_ai"],
        suggested_languages=["en"],
        model_routing={
            "latin": "grok-4.3",
            "cyrillic": "gemini-2.5-flash",
            "cjk": "grok-4.3",
            "arabic": "gemini-2.5-flash",
            "greek": "gemini-2.5-flash",
        },
    ),
    "books": DocumentProfile(
        name="books",
        system_prompt=_BOOKS_PROMPT,
        description=(
            "Book page. Preserves front/back matter, block quotes, epigraphs, "
            "dialogue formatting, scene breaks, illustrations with captions, "
            "cross-references, and multi-column layout. Add surya2 for "
            "layout analysis of complex page designs and illustrations. "
            "Uses Gemini for rich blockquote/header markup on Latin script."
        ),
        suggested_engines=["marker", "tesseract"],
        optional_engines=["surya2"],
        suggested_languages=["en"],
        model_routing={
            "latin": "gemini-2.5-flash",
            "cyrillic": "gemini-2.5-flash",
            "cjk": "grok-4.3",
            "arabic": "gemini-2.5-flash",
            "greek": "gemini-2.5-flash",
        },
    ),
    "grok-value": DocumentProfile(
        name="grok-value",
        system_prompt=_GENERAL_PROMPT,
        description=(
            "Cost-optimized Grok pipeline. Uses grok-4.3 ($0.006/page) for all "
            "scripts — 78% MMMU-Pro vision benchmark at the lowest cost among "
            "competitive VLMs. Best for: CJK documents, batch processing, "
            "cost-sensitive pipelines. Skip for: books with complex blockquote "
            "structure (Gemini is semantically richer)."
        ),
        suggested_engines=["marker", "tesseract"],
        optional_engines=["surya2", "mathpix", "google_doc_ai", "trocr"],
        suggested_languages=["en"],
        model_routing={
            "latin": "grok-4.3",
            "cyrillic": "grok-4.3",
            "cjk": "grok-4.3",
            "arabic": "grok-4.3",
            "greek": "grok-4.3",
        },
    ),
    "grok-quality": DocumentProfile(
        name="grok-quality",
        system_prompt=_GENERAL_PROMPT,
        description=(
            "Maximum-quality Grok pipeline. Uses grok-4.5 ($0.013/page, 80% "
            "MMMU-Pro) — Grok's flagship model with fastest end-to-end response "
            "(19.2s), competitive with Gemini 3.5 Flash on vision benchmarks. "
            "Best for: academic publications, mathematical proofs, technical "
            "specifications where merge quality justifies the premium."
        ),
        suggested_engines=["marker", "tesseract", "mathpix"],
        optional_engines=["surya2", "google_doc_ai", "trocr"],
        suggested_languages=["en"],
        model_routing={
            "latin": "grok-4.5",
            "cyrillic": "grok-4.5",
            "cjk": "grok-4.5",
            "arabic": "grok-4.5",
            "greek": "grok-4.5",
        },
    ),
}


# ── User-extensible profile loading ─────────────────────────────────────────

_USER_PROFILES: dict[str, DocumentProfile] = {}


def load_user_profiles(profiles_dir: Path) -> dict[str, DocumentProfile]:
    """Load user-defined profiles from YAML files in *profiles_dir*.

    Returns a dict of profile name to :class:`DocumentProfile`.  Files that
    fail to parse are logged as warnings and skipped.
    """
    if not profiles_dir.is_dir():
        return {}

    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML required for user profiles; install with: uv add pyyaml")
        return {}

    loaded: dict[str, DocumentProfile] = {}
    for yaml_file in sorted(profiles_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "name" not in data or "system_prompt" not in data:
                logger.warning("Skipping %s: missing required 'name' or 'system_prompt'", yaml_file)
                continue
            profile = DocumentProfile(
                name=data["name"],
                system_prompt=data["system_prompt"],
                description=data.get("description", ""),
                suggested_engines=data.get("suggested_engines", ["marker"]),
                optional_engines=data.get("optional_engines", ["tesseract"]),
                suggested_languages=data.get("suggested_languages", ["en"]),
                model_routing=data.get("model_routing", {}),
            )
            loaded[profile.name] = profile
            logger.info("Loaded user profile '%s' from %s", profile.name, yaml_file)
        except Exception as exc:
            logger.warning("Failed to load user profile from %s: %s", yaml_file, exc)
    return loaded


def _init_user_profiles() -> None:
    """Load user profiles from ``./profiles/`` (relative to CWD)."""
    global _USER_PROFILES
    _USER_PROFILES = load_user_profiles(Path("profiles"))


# ── Public API ──────────────────────────────────────────────────────────────


def get_profile(name: str) -> DocumentProfile:
    """Return the :class:`DocumentProfile` for *name*.

    Checks user-defined profiles first, then built-in.  Falls back to
    ``"general"`` if *name* is not found.
    """
    if name in _USER_PROFILES:
        return _USER_PROFILES[name]
    if name not in PROFILES and name not in _USER_PROFILES:
        logger.warning(
            "Unknown profile '%s' — falling back to 'general'. Valid: %s",
            name,
            ", ".join(sorted(PROFILES.keys())),
        )
    return (
        PROFILES.get(name, PROFILES["general"])
        if name not in _USER_PROFILES
        else _USER_PROFILES[name]
    )


def list_profiles() -> list[str]:
    """Return the sorted list of registered profile names (built-in + user)."""
    return sorted(set(PROFILES.keys()) | set(_USER_PROFILES.keys()))


# ── Module init ─────────────────────────────────────────────────────────────

_init_user_profiles()
