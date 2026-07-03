"""HTML document source — web content with metadata extraction.

Parses HTML content and extracts:
- Text content (via lxml text_content)
- Schema.org JSON-LD metadata (``<script type="application/ld+json">``)
- Highwire Press / DC / Open Graph meta tags
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

_SCRIPT_RE = re.compile(
    r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)


class HtmlSource(DocumentSource):
    """Document source for HTML files (``.html``, ``.htm``, ``.xhtml``).

    Extracts text content via lxml and parses embedded metadata
    (schema.org JSON-LD, meta tags).  A single file is a 1-page document.
    """

    has_native_metadata: bool = True

    _text_cache: str | None = None
    _meta_cache: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        return "html"

    @property
    def source_mimetype(self) -> str:
        return "text/html"

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> tuple[str, dict[str, str]]:
        if self._text_cache is not None and self._meta_cache is not None:
            return self._text_cache, self._meta_cache

        raw = self.path.read_text(encoding="utf-8", errors="replace")

        # Extract JSON-LD
        meta: dict[str, str] = {}
        for m in _SCRIPT_RE.finditer(raw):
            try:
                ld = json.loads(m.group(1))
                if isinstance(ld, dict):
                    self._extract_ld(ld, meta)
                elif isinstance(ld, list):
                    for item in ld:
                        if isinstance(item, dict):
                            self._extract_ld(item, meta)
            except json.JSONDecodeError:
                pass

        # Parse HTML for meta tags and text
        try:
            from lxml import html as lxml_html

            doc = lxml_html.document_fromstring(raw)

            # Meta tags
            for el in doc.xpath("//meta[@name]"):
                name = el.get("name", "").lower()
                content = el.get("content", "")
                if (
                    name.startswith("citation_")
                    or name.startswith("dc.")
                    or name.startswith("dcterms.")
                ):
                    meta.setdefault(name, content)
                elif name in ("author", "description", "keywords", "date"):
                    meta.setdefault(name, content)

            # Open Graph
            for el in doc.xpath("//meta[@property]"):
                prop = el.get("property", "").lower()
                content = el.get("content", "")
                if prop.startswith("og:"):
                    meta.setdefault(prop, content)

            # Title tag
            title_el = doc.xpath("//title")
            if title_el and title_el[0].text:
                meta.setdefault("title", title_el[0].text.strip())

            # Text content
            self._text_cache = doc.text_content().strip()
        except Exception:
            # Fallback: strip HTML tags
            self._text_cache = re.sub(r"<[^>]+>", " ", raw)
            self._text_cache = re.sub(r"\s+", " ", self._text_cache).strip()

        self._meta_cache = meta
        return self._text_cache, meta

    @staticmethod
    def _extract_ld(ld: dict, meta: dict) -> None:
        """Extract metadata from a JSON-LD object into the flat meta dict."""
        for key in ("name", "headline", "title"):
            if ld.get(key):
                meta.setdefault("title", str(ld[key]))

        author = ld.get("author")
        if isinstance(author, dict) and author.get("name"):
            meta.setdefault("author", str(author["name"]))
        elif isinstance(author, list) and author and isinstance(author[0], dict):
            meta.setdefault("author", str(author[0].get("name", "")))
        elif isinstance(author, str):
            meta.setdefault("author", author)

        if ld.get("datePublished"):
            meta.setdefault("date", str(ld["datePublished"]))
        elif ld.get("dateCreated"):
            meta.setdefault("date", str(ld["dateCreated"]))

        if ld.get("description"):
            meta.setdefault("description", str(ld["description"]))

        if ld.get("publisher"):
            pub = ld["publisher"]
            if isinstance(pub, dict) and pub.get("name"):
                meta.setdefault("publisher", str(pub["name"]))
            elif isinstance(pub, str):
                meta.setdefault("publisher", pub)

        if ld.get("license"):
            meta.setdefault("license", str(ld["license"]))

        if ld.get("isAccessibleForFree"):
            meta.setdefault("open_access", str(ld["isAccessibleForFree"]))

    def extract_metadata(self) -> MetadataResult:
        _text, meta = self._parse()

        # Map citation_* and dc.* meta keys to standard names
        title = (
            meta.get("title", "")
            or meta.get("citation_title", "")
            or meta.get("dc.title", "")
            or meta.get("og:title", "")
        )
        authors: list[str] = []
        author = meta.get("author") or meta.get("citation_author") or meta.get("dc.creator")
        if author:
            authors = [author]
        publisher = (
            meta.get("publisher") or meta.get("dc.publisher") or meta.get("citation_publisher", "")
        )
        date = meta.get("date") or meta.get("citation_date") or meta.get("dc.date", "")

        return MetadataResult(
            title=title,
            authors=authors,
            date=date,
            language=meta.get("dc.language", meta.get("language", "")),
            publisher=publisher,
            document_type="webpage",
            extraction_method="html-metadata",
            source_info=SourceInfo(
                format="html",
                page_count=1,
                mimetype="text/html",
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError(
            "HtmlSource.render_page not supported — use a headless browser or convert to PDF first."
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _meta = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
