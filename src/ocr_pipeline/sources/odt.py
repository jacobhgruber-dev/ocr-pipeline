"""ODT document source — OpenDocument Text (LibreOffice / OpenOffice).

Parses ODT archives (ZIP containers with content.xml) via lxml.
"""

from __future__ import annotations

import logging
from pathlib import Path
from zipfile import ZipFile

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

_NS_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_NS_OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
_NS_META = "{urn:oasis:names:tc:opendocument:xmlns:meta:1.0}"
_NS_DC = "{http://purl.org/dc/elements/1.1/}"


class OdtSource(DocumentSource):
    """Document source for OpenDocument Text files (``.odt``).

    Parses the embedded content.xml for text and meta.xml for metadata.
    """

    _text_cache: str | None = None
    _meta_cache: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        return "odt"

    @property
    def source_mimetype(self) -> str:
        return "application/vnd.oasis.opendocument.text"

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> tuple[str, dict[str, str]]:
        if self._text_cache is not None and self._meta_cache is not None:
            return self._text_cache, self._meta_cache

        from lxml import etree

        meta: dict[str, str] = {}
        text_parts: list[str] = []

        with ZipFile(str(self.path), "r") as zf:
            # Parse meta.xml
            if "meta.xml" in zf.namelist():
                try:
                    meta_xml = etree.fromstring(zf.read("meta.xml"))
                    for el in meta_xml.iter():
                        tag = etree.QName(el.tag).localname
                        if tag in (
                            "title",
                            "creator",
                            "subject",
                            "description",
                            "language",
                            "date",
                        ):
                            if el.text:
                                meta[tag] = el.text.strip()

                    # Dublin Core in meta.xml
                    for el in meta_xml.iter(f"{_NS_DC}title"):
                        if el.text:
                            meta["title"] = el.text.strip()
                    for el in meta_xml.iter(f"{_NS_DC}creator"):
                        if el.text:
                            meta.setdefault("author", el.text.strip())
                except Exception:
                    pass

            # Parse content.xml
            if "content.xml" in zf.namelist():
                try:
                    content_xml = etree.fromstring(zf.read("content.xml"))
                    for el in content_xml.iter():
                        if el.tag in (f"{_NS_TEXT}p", f"{_NS_TEXT}h"):
                            if el.text:
                                text_parts.append(el.text.strip())
                            for child in el:
                                if child.tail:
                                    text_parts.append(child.tail.strip())
                except Exception:
                    pass

        self._text_cache = "\n\n".join(p for p in text_parts if p)
        self._meta_cache = meta
        return self._text_cache, meta

    def extract_metadata(self) -> MetadataResult:
        _text, meta = self._parse()
        st = self.path.stat()

        return MetadataResult(
            title=meta.get("title", ""),
            authors=[meta["author"]]
            if "author" in meta
            else ([meta["creator"]] if "creator" in meta else []),
            date=meta.get("date", ""),
            language=meta.get("language", ""),
            document_type="document",
            extraction_method="odt-parsing",
            source_info=SourceInfo(
                format="odt",
                page_count=1,
                mimetype="application/vnd.oasis.opendocument.text",
                extra={"file_size_bytes": st.st_size},
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("OdtSource.render_page not supported — convert to PDF first.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _meta = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
