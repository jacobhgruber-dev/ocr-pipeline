"""Citation patterns the OCR pipeline must preserve intact.

This module documents the citation-critical patterns that downstream
systems (ScholiaCite, academic databases) depend on. These patterns
are used by the VLM system prompts and citation-preservation post-processing.

Source: ScholiaCite citation engine (CITATION_NOTES.md, JOURNAL_STYLE_OVERRIDES.md,
DEEPSEEK_MASTER_PROMPT.md) and Academic Research MCP citation audit findings.
"""

from __future__ import annotations

# ── Vatican / Papal ──────────────────────────────────────────────
PAPAL_DOCUMENT_TYPES: list[str] = [
    "apostolic constitution",
    "dogmatic constitution",
    "encyclical",
    "apostolic exhortation",
    "apostolic letter",
    "motu proprio",
    "pastoral constitution",
    "decree",
    "declaration",
    "instruction",
    "rescript",
    "general audience",
    "homily",
    "address",
    "speech",
    "allocution",
    "angelus",
    "regina caeli",
    "message",
    "catechism",
    "canon law",
]

POPE_NAMES: list[str] = [
    "PAUL VI",
    "PIUS XII",
    "LEO XIII",
    "JOHN XXIII",
    "JOHN PAUL II",
    "BENEDICT XVI",
    "FRANCIS",
    "PIUS XI",
    "BENEDICT XV",
    "PIUS X",
    "LEO XII",
    "GREGORY XVI",
    "INNOCENT III",
    "BONIFACE VIII",
]

# ── Reference Systems ────────────────────────────────────────────
DENZINGER_PATTERNS: list[str] = [
    r"DS\s+\d+",  # DS 150
    r"Denz\.\s+\d+",  # Denz. 150
    r"DH\s+\d+",  # DH 150 (Denzinger-Hünermann)
]

AAS_PATTERN: str = r"AAS\s+\d+\s*\(\d{4}\)\s*\d+[-–—]\d+"

CANON_LAW_PATTERNS: list[str] = [
    r"can\.\s+\d+(\s*§\s*\d+)?",  # can. 123 §2
    r"CIC/1983\s+c\.\s+\d+",  # CIC/1983 c. 1055
    r"CCEO\s+c\.\s+\d+",  # CCEO c. 1171
    r"CIC/1917\s+c\.\s+\d+",  # CIC/1917
]

# ── Ancient / Patristic ───────────────────────────────────────────
PATRISTIC_ABBREVIATIONS: dict[str, str] = {
    "Conf.": "Confessions (Augustine)",
    "De Civ. Dei": "De Civitate Dei (Augustine)",
    "ST": "Summa Theologiae (Aquinas)",
    "SCG": "Summa Contra Gentiles (Aquinas)",
    "Ant.": "Jewish Antiquities (Josephus)",
    "Hist. eccl.": "Historia Ecclesiastica (Eusebius)",
}

# ── Citation-Sensitive Characters ─────────────────────────────────
# Characters that must never be corrupted or replaced during OCR/post-processing
CITATION_SENSITIVE_CHARS: dict[str, str] = {
    "\u00a7": "section symbol (§) — used in Vatican/canon law citations",
    "\u2013": "en dash (–) — used in page ranges per CMOS 18",
    "\u2014": "em dash (—) — used in sentence breaks",
    "\u2019": "right single quote (') — used in Italian/Latin titles",
    "\u00b6": "pilcrow (¶) — used in some citation formats",
}

# ── Aquinas Abbreviations ─────────────────────────────────────────
AQUINAS_ABBREVIATIONS: list[str] = [
    "ST",
    "SCG",
    "De ente",
    "Cat. aur.",
    "In Meta.",
    "Comp. theol.",
]

# ── Liturgical Texts ──────────────────────────────────────────────
LITURGICAL_TEXTS: list[str] = [
    "Roman Missal",
    "Missale Romanum",
    "Lectionary for Mass",
    "Divine Office",
    "Liturgia Horarum",
    "Roman Ritual",
    "Roman Pontifical",
    "GIRM",
    "Roman Gradual",
    "Ceremonial of Bishops",
]

# ── Patterns That Post-Processing Must Not Break ──────────────────
# Regex patterns for content that must survive ALL post-processing steps
CITATION_PRESERVATION_PATTERNS: list[str] = [
    # Roman numeral Pope names
    r"\b(?:PAUL|PIUS|LEO|JOHN|BENEDICT|GREGORY|INNOCENT|BONIFACE)\s+(?:VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XXIII)\b",
    # Denzinger/DS references
    r"\b(?:DS|Denz\.|DH)\s+\d+\b",
    # AAS references
    r"AAS\s+\d+\s*\(\d{4}\)\s*\d+[-–—]\d+",
    # Canon law citations
    r"\b(?:can\.|c\.)\s+\d+(?:\s*§\s*\d+)?\b",
    r"\bCIC/\d{4}\s+c\.\s+\d+\b",
    # DOIs
    r"10\.\d{4,}/[^\s]+",
    # Aquinas citations
    r"\b(?:ST|SCG|De ente|Cat\. aur\.|In Meta\.|Comp\. theol\.)\b",
    # Ancient source abbreviations
    r"\b(?:1QS|1\s*En\.|Ign\.\s*Eph\.|Gos\.\s*Thom\.|m\.\s*Ber\.|b\.\s*Ber\.)\b",
    # Parenthetical series references
    r"\((?:NPNF\d?|LCL|COS|ABD|BNTC)\s[^)]+\)",
]

# ── OCR Damage Patterns to Detect ─────────────────────────────────
# Each entry is (damaged_form, correct_form, description).  Used by
# PostProcessor.validate_citations() to flag common OCR mistakes.
OCR_DAMAGE_CHECKS: list[tuple[str, str, str]] = [
    # Roman numeral Pope names corrupted by lowercasing
    ("Paul Vi", "PAUL VI", "Pope name roman numeral lowered and misspaced"),
    ("Pius Xii", "PIUS XII", "Pope name roman numeral lowered and misspaced"),
    ("Leo Xiii", "LEO XIII", "Pope name roman numeral lowered and misspaced"),
    ("John Xxiii", "JOHN XXIII", "Pope name roman numeral lowered"),
    ("John Paul Ii", "JOHN PAUL II", "Pope name roman numeral lowered"),
    ("Benedict Xvi", "BENEDICT XVI", "Pope name roman numeral lowered"),
    # Dashes replacing en dashes in number ranges
    ("AAS", "AAS", "placeholder — AAS check handled by regex"),
    # Denzinger corruption
    ("Denz .", "Denz.", "Denzinger abbreviation corrupted"),
    ("ds", "DS", "Denzinger-Schönmetzer prefix lowered"),
    ("dh", "DH", "Denzinger-Hünermann prefix lowered"),
    # Abbreviation period loss
    ("can ", "can. ", "canon law abbreviation missing period (word-initial)"),
    ("Ant ", "Ant.", "Josephus abbreviation missing period (word-initial)"),
    ("Conf ", "Conf.", "Augustine abbreviation missing period (word-initial)"),
]
