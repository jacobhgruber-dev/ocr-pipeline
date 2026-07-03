"""TEI XML document source — Text Encoding Initiative scholarly documents.

TEI is the standard XML format for digital scholarly editions,
used by libraries, archives, and academic projects worldwide.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

_NS_TEI = "{http://www.tei-c.org/ns/1.0}"


class TeiSource(DocumentSource):
    """Document source for TEI XML files (``.tei``, ``.xml`` with TEI namespace).

    Extracts structured text from TEI body, metadata from the TEI header
    (titleStmt, publicationStmt, sourceDesc).
    """

    _text_cache: str | None = None
    _meta_cache: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        return "tei"

    @property
    def source_mimetype(self) -> str:
        return "application/tei+xml"

    @property
    def page_count(self) -> int:
        return 1

    def _is_tei(self) -> bool:
        """Quick check: does this XML file use the TEI namespace?"""
        try:
            raw = self.path.read_text(encoding="utf-8", errors="replace")[:2000]
            return "tei-c.org" in raw or "TEI" in raw
        except Exception:
            return False

    def _parse(self) -> tuple[str, dict[str, str]]:
        if self._text_cache is not None:
            return self._text_cache, self._meta_cache or {}

        from lxml import etree

        meta: dict[str, str] = {}
        text_parts: list[str] = []

        try:
            raw = self.path.read_text(encoding="utf-8", errors="replace")
            doc = etree.fromstring(raw.encode("utf-8"))
            ns = _NS_TEI

            # --- Header metadata ---
            header = doc.find(f"{ns}teiHeader") or doc.find("teiHeader")
            if header is not None:
                # Title
                for title_el in header.iter(f"{ns}title"):
                    title_text = "".join(title_el.itertext()).strip()
                    if title_text and "title" not in meta:
                        meta["title"] = title_text
                        break

                # Author
                authors: list[str] = []
                for author_el in header.iter(f"{ns}author"):
                    name_parts = []
                    for child in author_el.iter():
                        tag = etree.QName(child.tag).localname
                        if tag in ("forename", "surname", "name", "persName"):
                            if child.text:
                                name_parts.append(child.text.strip())
                    if name_parts:
                        authors.append(" ".join(name_parts))
                if authors:
                    meta["author"] = "; ".join(authors)

                # Publication info
                for pub_el in header.iter(f"{ns}publisher"):
                    if pub_el.text:
                        meta.setdefault("publisher", pub_el.text.strip())
                for date_el in header.iter(f"{ns}date"):
                    if date_el.text and "date" not in meta:
                        meta["date"] = date_el.text.strip()

                # Language
                for lang_el in header.iter(f"{ns}language"):
                    ident = lang_el.get("ident", "")
                    if ident:
                        meta["language"] = ident

            # --- Body text ---
            body = doc.find(f"{ns}text/{ns}body") or doc.find("text/body")
            if body is not None:
                for el in body.iter():
                    tag = etree.QName(el.tag).localname
                    if tag in ("p", "head", "l", "ab", "seg", "item", "cell"):
                        content = (el.text or "").strip()
                        if content:
                            text_parts.append(content)
                    elif tag == "lb":
                        if el.tail:
                            text_parts.append(el.tail.strip())

            # Fallback: entire body text_content
            if not text_parts and body is not None:
                self._text_cache = "".join(body.itertext()).strip()
            else:
                self._text_cache = "\n\n".join(text_parts)

        except Exception as exc:
            logger.warning("TEI parsing failed for %s: %s", self.path.name, exc)
            self._text_cache = self.path.read_text(encoding="utf-8", errors="replace")

        self._meta_cache = meta
        return self._text_cache, meta

    def extract_metadata(self) -> MetadataResult:
        _text, meta = self._parse()

        return MetadataResult(
            title=meta.get("title", ""),
            authors=[meta["author"]] if "author" in meta else [],
            date=meta.get("date", ""),
            language=meta.get("language", ""),
            publisher=meta.get("publisher", ""),
            document_type="tei-document",
            extraction_method="tei-parsing",
            source_info=SourceInfo(
                format="tei",
                page_count=1,
                mimetype="application/tei+xml",
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("TeiSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _meta = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
