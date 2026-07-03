"""Apple Pages document source (.pages).

Modern .pages files are ZIP containers with an index.xml and data
files.  Legacy .pages files are single binary packages.

Text extraction from modern .pages via lxml on the internal index.xml.
"""

from __future__ import annotations

import logging
from pathlib import Path
from zipfile import ZipFile

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class PagesSource(DocumentSource):
    """Document source for Apple Pages files (``.pages``).

    Parses the internal index.xml from the ZIP container for text.
    """

    _text_cache: str | None = None
    _meta_cache: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        return "pages"

    @property
    def source_mimetype(self) -> str:
        return "application/x-iwork-pages-sffpages"

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
            with ZipFile(str(self.path), "r") as zf:
                if "index.xml" not in zf.namelist():
                    # Legacy .pages format — not a ZIP
                    self._text_cache = (
                        "[Legacy .pages format — please re-save as modern .pages or export to PDF]"
                    )
                    self._meta_cache = {}
                    return self._text_cache, {}

                xml_bytes = zf.read("index.xml")
                doc = etree.fromstring(xml_bytes)

                # Extract text from all text storage elements
                for el in doc.iter():
                    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
                    if tag in ("sf:text-storage", "sf:text-body"):
                        body_text = "".join(el.itertext())
                        if body_text.strip():
                            text_parts.append(body_text.strip())

                # Try to find title from metadata
                for meta_el in doc.iter():
                    if "document-title" in str(meta_el.tag) and meta_el.text:
                        meta["title"] = meta_el.text.strip()

        except Exception as exc:
            logger.warning("Pages parsing failed for %s: %s", self.path.name, exc)

        self._text_cache = "\n\n".join(text_parts) or self.path.read_text(
            encoding="utf-8", errors="replace"
        )
        self._meta_cache = meta
        return self._text_cache, meta

    def extract_metadata(self) -> MetadataResult:
        _text, meta = self._parse()

        return MetadataResult(
            title=meta.get("title", "") or self.path.stem,
            document_type="pages-document",
            extraction_method="pages-parsing",
            source_info=SourceInfo(
                format="pages",
                page_count=1,
                mimetype="application/x-iwork-pages-sffpages",
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("PagesSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _meta = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
