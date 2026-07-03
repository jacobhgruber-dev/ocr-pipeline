"""LaTeX document source — academic preprints and manuscripts.

Extracts text content and metadata (``\\title{}``, ``\\author{}``,
``\\date{}``, ``\\abstract``) from LaTeX source files.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

# Patterns for metadata extraction
_TITLE_PAT = re.compile(r"\\title\s*\{(.+?)\}(?<!\\)", re.DOTALL)
_AUTHOR_PAT = re.compile(r"\\author\s*\{(.+?)\}(?<!\\)", re.DOTALL)
_DATE_PAT = re.compile(r"\\date\s*\{(.+?)\}(?<!\\)", re.DOTALL)
_ABSTRACT_ENV = re.compile(r"\\begin\{abstract\}(.+?)\\end\{abstract\}", re.DOTALL)
_DOCUMENT_BODY = re.compile(r"\\begin\{document\}(.+?)\\end\{document\}", re.DOTALL)
_COMMAND_RE = re.compile(r"\\(?:[a-zA-Z]+|.)(?:\{[^}]*\})*")
_COMMENT_RE = re.compile(r"(?<!\\)%.*$", re.MULTILINE)


class LatexSource(DocumentSource):
    """Document source for LaTeX files (``.tex``).

    Strips LaTeX commands to extract readable text and parses structural
    metadata (title, author, abstract).  A single file is a 1-page document.
    """

    _text_cache: str | None = None
    _meta_cache: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        return "latex"

    @property
    def source_mimetype(self) -> str:
        return "application/x-latex"

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> tuple[str, dict[str, str]]:
        if self._text_cache is not None and self._meta_cache is not None:
            return self._text_cache, self._meta_cache

        raw = self.path.read_text(encoding="utf-8", errors="replace")
        meta: dict[str, str] = {}

        # Extract metadata
        for pat, key in [
            (_TITLE_PAT, "title"),
            (_AUTHOR_PAT, "author"),
            (_DATE_PAT, "date"),
        ]:
            m = pat.search(raw)
            if m:
                meta[key] = _strip_braces(m.group(1).strip())

        # Extract abstract
        abs_m = _ABSTRACT_ENV.search(raw)
        if abs_m:
            meta["abstract"] = _strip_commands(abs_m.group(1).strip())

        # Extract document body text (strip commands, keep content)
        body_m = _DOCUMENT_BODY.search(raw)
        if body_m:
            text = body_m.group(1)
        else:
            text = raw

        self._text_cache = _strip_commands(_COMMENT_RE.sub("", text)).strip()
        self._meta_cache = meta
        return self._text_cache, meta

    def extract_metadata(self) -> MetadataResult:
        _text, meta = self._parse()

        return MetadataResult(
            title=meta.get("title", ""),
            authors=[meta["author"]] if "author" in meta else [],
            date=meta.get("date", ""),
            document_type="preprint" if "arxiv" in str(self.path).lower() else "manuscript",
            extraction_method="latex-parsing",
            source_info=SourceInfo(
                format="latex",
                page_count=1,
                mimetype="application/x-latex",
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("LatexSource.render_page not supported — compile to PDF first.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _meta = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path


def _strip_braces(text: str) -> str:
    """Strip LaTeX grouping braces from text, preserving inner content."""
    depth = 0
    result: list[str] = []
    for c in text:
        if c == "{":
            depth += 1
            continue
        elif c == "}":
            if depth > 0:
                depth -= 1
            else:
                result.append(c)
            continue
        result.append(c)
    return "".join(result)


def _strip_commands(text: str) -> str:
    """Remove LaTeX commands while preserving argument content.

    ``\\textbf{hello}`` → ``hello``
    ``\\emph{world}`` → ``world``
    ``\\section{Title}`` → ``Title``
    """

    # Simple approach: replace commands with their argument content
    def _replacer(m: re.Match) -> str:
        cmd = m.group(0)
        # Extract content within braces
        inner = re.findall(r"\{((?:[^{}]|\{[^{}]*\})*)\}", cmd)
        if inner:
            return inner[-1]
        # Commands without braces keep their text
        return ""

    result = _COMMAND_RE.sub(_replacer, text)
    # Clean up extra whitespace
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r" {2,}", " ", result)
    return result
