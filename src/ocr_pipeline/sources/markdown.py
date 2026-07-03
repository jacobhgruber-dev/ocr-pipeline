"""Markdown document source with YAML frontmatter extraction.

Parses YAML frontmatter (delimited by ``---``) for title, author, date,
and other metadata.  The markdown body is the extractable text.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ocr_pipeline.models import MetadataResult, RightsInfo, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


_YAML_DELIM = re.compile(r"^---\s*$", re.MULTILINE)
_STRIP_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)


class MarkdownSource(DocumentSource):
    """Document source for Markdown files (``.md``, ``.markdown``).

    Parses YAML frontmatter for metadata and uses the remaining body
    as extractable text.  A single file is a 1-page document.
    """

    has_native_metadata: bool = True

    _text_cache: str | None = None
    _frontmatter: dict[str, object] | None = None

    @property
    def source_format(self) -> str:
        return "markdown"

    @property
    def source_mimetype(self) -> str:
        return "text/markdown"

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> tuple[str, dict[str, object]]:
        """Read the file, extract frontmatter, return (body, frontmatter_dict)."""
        if self._text_cache is not None:
            return self._text_cache, self._frontmatter or {}

        text = self._read_raw()
        frontmatter: dict[str, object] = {}

        # Split on YAML delimiters
        parts = _YAML_DELIM.split(text, maxsplit=2)
        if len(parts) >= 3 and text.startswith("---"):
            yaml_block = parts[1].strip()
            text = parts[2].strip() if len(parts) > 2 else ""
            try:
                import yaml as _yaml

                parsed = _yaml.safe_load(yaml_block)
                if isinstance(parsed, dict):
                    frontmatter = parsed
            except ImportError:
                logger.debug("PyYAML not available — skipping frontmatter parsing")
                frontmatter = {"_raw_frontmatter": yaml_block}
            except Exception:
                frontmatter = {"_raw_frontmatter": yaml_block}
        else:
            # No frontmatter — check if text starts with <!-- doc: metadata comment
            comment_match = re.match(r"^<!--\s*doc:(.*?)-->", text)
            if comment_match:
                meta_str = comment_match.group(1).strip()
                for part in meta_str.split("|"):
                    part = part.strip()
                    if ":" in part:
                        k, v = part.split(":", 1)
                        frontmatter[k.strip()] = v.strip()

        self._text_cache = _STRIP_COMMENTS.sub("", text).strip()
        self._frontmatter = frontmatter
        return self._text_cache, frontmatter

    def _read_raw(self) -> str:
        """Detect encoding and read the raw file content."""
        try:
            from charset_normalizer import from_path

            results = from_path(str(self.path))
            if results:
                return str(results.best())
        except Exception:
            pass
        return self.path.read_text(encoding="utf-8")

    def extract_metadata(self) -> MetadataResult:
        _body, fm = self._parse()
        st = self.path.stat()

        meta = MetadataResult(
            title=str(fm.get("title", fm.get("Title", ""))),
            authors=[str(fm["author"])]
            if "author" in fm
            else ([str(fm["Author"])] if "Author" in fm else []),
            language=str(fm.get("lang", fm.get("language", ""))),
            date=str(fm.get("date", fm.get("Date", ""))),
            document_type=str(fm.get("type", fm.get("document_type", ""))),
            extraction_method="frontmatter",
            source_info=SourceInfo(
                format="markdown",
                page_count=1,
                mimetype="text/markdown",
                extra={
                    "file_path": str(self.path),
                    "file_size_bytes": st.st_size,
                    "modified": str(st.st_mtime),
                },
            ),
        )
        if "license" in fm or "license_url" in fm:
            meta.rights = RightsInfo(
                license=str(fm.get("license", "")),
                license_url=str(fm.get("license_url", "")),
            )
        return meta

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError(
            "MarkdownSource.render_page not supported — convert to PDF/image before OCR."
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _fm = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
