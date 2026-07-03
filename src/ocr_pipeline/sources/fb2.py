"""FictionBook (.fb2) document source — XML-based e-book format.

FictionBook is popular in Russian-speaking countries and Eastern Europe.
It stores the entire book in a single XML file with structured metadata,
sections, and inline formatting.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

_NS_FB = "{http://www.gribuser.ru/xml/fictionbook/2.0}"


class Fb2Source(DocumentSource):
    """Document source for FictionBook files (``.fb2``).

    Parses structured XML: description (title-info, document-info,
    publish-info) for metadata, body sections for text.
    """

    _text_cache: str | None = None
    _meta_cache: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        return "fb2"

    @property
    def source_mimetype(self) -> str:
        return "application/x-fictionbook+xml"

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> tuple[str, dict[str, str]]:
        if self._text_cache is not None:
            return self._text_cache, self._meta_cache or {}

        from lxml import etree

        meta: dict[str, str] = {}
        text_parts: list[str] = []

        try:
            raw = self.path.read_text(encoding="utf-8", errors="replace")
            parser = etree.XMLParser(resolve_entities=False, no_network=True)
            doc = etree.fromstring(raw.encode("utf-8"), parser)
            ns = _NS_FB

            # --- Metadata ---
            desc = doc.find(f"{ns}description")
            if desc is not None:
                title_info = desc.find(f"{ns}title-info")
                if title_info is not None:
                    for tag, key in [
                        ("book-title", "title"),
                        ("annotation", "description"),
                        ("keywords", "keywords"),
                        ("lang", "language"),
                    ]:
                        el = title_info.find(f"{ns}{tag}")
                        if el is not None and el.text:
                            meta[key] = el.text.strip()

                    # Authors
                    authors: list[str] = []
                    for author in title_info.iter(f"{ns}author"):
                        first = author.find(f"{ns}first-name")
                        last = author.find(f"{ns}last-name")
                        middle = author.find(f"{ns}middle-name")
                        name_parts = []
                        if first is not None and first.text:
                            name_parts.append(first.text.strip())
                        if middle is not None and middle.text:
                            name_parts.append(middle.text.strip())
                        if last is not None and last.text:
                            name_parts.append(last.text.strip())
                        if name_parts:
                            authors.append(" ".join(name_parts))
                    if authors:
                        meta["author"] = "; ".join(authors)

                    # Genre
                    genres: list[str] = []
                    for genre in title_info.iter(f"{ns}genre"):
                        if genre.text:
                            genres.append(genre.text.strip())
                    if genres:
                        meta["genre"] = ", ".join(genres)

                # ISBN (in publish-info)
                pub_info = desc.find(f"{ns}publish-info")
                if pub_info is not None:
                    for isbn_el in pub_info.iter(f"{ns}isbn"):
                        if isbn_el.text:
                            meta["isbn"] = isbn_el.text.strip()
                            break
                    for publisher_el in pub_info.iter(f"{ns}publisher"):
                        if publisher_el.text:
                            meta["publisher"] = publisher_el.text.strip()
                            break
                    for year_el in pub_info.iter(f"{ns}year"):
                        if year_el.text:
                            meta["date"] = year_el.text.strip()
                            break

                # Document info
                doc_info = desc.find(f"{ns}document-info")
                if doc_info is not None:
                    for date_el in doc_info.iter(f"{ns}date"):
                        val = date_el.get("value", "")
                        if val and "date" not in meta:
                            meta["date"] = val
                            break

            # --- Body text ---
            for body in doc.iter(f"{ns}body"):
                body_name = body.get("name", "")
                if body_name:
                    text_parts.append(f"## {body_name}")

                for section in body.iter(f"{ns}section"):
                    for title_el in section.iter(f"{ns}title"):
                        for p in title_el.iter(f"{ns}p"):
                            if p.text:
                                text_parts.append(f"### {p.text.strip()}")
                    for p in section.iter(f"{ns}p"):
                        if p.text:
                            text_parts.append(p.text.strip())

            for note_body in doc.iter(f"{ns}body"):
                note_name = note_body.get("name")
                if note_name == "notes":
                    for section in note_body.iter(f"{ns}section"):
                        section_id = section.get("id", "")
                        for p in section.iter(f"{ns}p"):
                            if p.text:
                                text_parts.append(f"[{section_id}] {p.text.strip()}")

        except Exception as exc:
            logger.warning("FB2 parsing failed for %s: %s", self.path.name, exc)

        self._text_cache = "\n\n".join(text_parts)
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
            isbn=meta.get("isbn", ""),
            document_type="ebook",
            extraction_method="fb2-parsing",
            keywords=meta.get("keywords", "").split(",") if meta.get("keywords") else [],
            source_info=SourceInfo(
                format="fb2",
                page_count=1,
                mimetype="application/x-fictionbook+xml",
                extra={
                    "genre": meta.get("genre", ""),
                },
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("Fb2Source.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _meta = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
