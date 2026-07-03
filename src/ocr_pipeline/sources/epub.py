"""EPUB document source — extract text and render pages from ebooks.

Uses ``ebooklib`` to parse the EPUB, then writes each chapter/section as a
rendered HTML block.  Text extraction walks the spine reading items in order.

DRM detection: checks the EPUB ZIP container for ``META-INF/encryption.xml``
(Adobe DRM) or ``META-INF/rights.xml`` (older DRM schemes).
"""

from __future__ import annotations

import logging
from pathlib import Path
from zipfile import ZipFile

from ocr_pipeline.errors import RenderError
from ocr_pipeline.models import MetadataResult, RightsInfo, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class EpubSource(DocumentSource):
    """Document source for EPUB 2/3 ebooks.

    Each "chapter" or spine item is treated as a logical page.  Text
    extraction strips HTML tags and returns plain text.  DRM detection
    checks for encryption.xml in the EPUB container.
    """

    _SPINE_ITEMS: list[tuple[str, str]] | None = None  # (item_id, href)
    _drm_cache: bool | None = None
    _book: object | None = None

    @property
    def source_format(self) -> str:
        return "epub"

    @property
    def source_mimetype(self) -> str:
        return "application/epub+zip"

    def has_drm(self) -> bool:
        """Check for Adobe DRM (encryption.xml) in the EPUB container."""
        if self._drm_cache is not None:
            return self._drm_cache
        try:
            with ZipFile(str(self.path), "r") as zf:
                names = zf.namelist()
                has_enc = "META-INF/encryption.xml" in names or "META-INF/rights.xml" in names
                self._drm_cache = has_enc
                return has_enc
        except Exception:
            self._drm_cache = False
            return False

    def extract_metadata(self) -> MetadataResult:
        """Extract EPUB OPF metadata, with DRM awareness."""
        try:
            from ebooklib import epub

            book = epub.read_epub(str(self.path))
        except Exception:
            return MetadataResult(
                title=self.path.stem,
                document_type="ebook",
                extraction_method="epub-detection",
                source_info=SourceInfo(format="epub", page_count=1),
            )

        meta = MetadataResult(
            title="",
            authors=[],
            language="",
            publisher="",
            date="",
            document_type="ebook",
            extraction_method="epub-opf",
            source_info=SourceInfo(
                format="epub",
                page_count=1,  # Default — updated below if possible
                mimetype="application/epub+zip",
            ),
        )
        try:
            meta.source_info.page_count = self.page_count
        except Exception:
            pass

        # DC metadata
        dc_titles = book.get_metadata("DC", "title")
        if dc_titles:
            meta.title = str(dc_titles[0][0])
        dc_creators = book.get_metadata("DC", "creator")
        if dc_creators:
            meta.authors = [str(c[0]) for c in dc_creators]
        dc_publisher = book.get_metadata("DC", "publisher")
        if dc_publisher:
            meta.publisher = str(dc_publisher[0][0])
        dc_date = book.get_metadata("DC", "date")
        if dc_date:
            meta.date = str(dc_date[0][0])
        dc_lang = book.get_metadata("DC", "language")
        if dc_lang:
            meta.language = str(dc_lang[0][0])
        dc_ids = book.get_metadata("DC", "identifier")
        for id_val in dc_ids:
            val = str(id_val[0])
            if val.startswith("urn:isbn:"):
                meta.isbn = val.replace("urn:isbn:", "")
            elif not meta.isbn and len(val) in (10, 13) and val.replace("-", "").isdigit():
                meta.isbn = val

        # DRM status
        has_drm = self.has_drm()
        if has_drm:
            meta.rights = RightsInfo(
                access_restrictions="Adobe DRM detected — text extraction may be limited"
            )
            meta.source_info.extra["has_drm"] = "true"
        else:
            meta.source_info.extra["has_drm"] = "false"

        return meta

    def _load_spine(self) -> list[tuple[str, str]]:
        """Parse the EPUB spine once and cache the ordered items."""
        if self._SPINE_ITEMS is not None:
            return self._SPINE_ITEMS

        from ebooklib import epub

        book = epub.read_epub(str(self.path))
        self._book = book
        spine: list[tuple[str, str]] = []

        for item_id, _linear in book.spine:
            item = book.get_item_with_id(item_id)
            if item is not None:
                spine.append((item_id, item.get_name()))

        self._SPINE_ITEMS = spine
        return spine

    @property
    def page_count(self) -> int:
        return len(self._load_spine())

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        """Render an EPUB spine item to a PNG via a headless browser.

        Falls back to a blank placeholder image when no browser is available.
        """
        raise NotImplementedError(
            "EpubSource.render_page not yet implemented — use a PDF conversion step before OCR."
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        from lxml import html as lxml_html

        spine = self._load_spine()
        if page_index < 0 or page_index >= len(spine):
            raise RenderError(f"EPUB page index {page_index} out of range ({len(spine)} items)")

        item_id, href = spine[page_index]
        book = self._book
        item = book.get_item_with_id(item_id)
        if item is None:
            raise RenderError(f"EPUB item {item_id} not found in {self.path}")

        content = item.get_content()
        # Decode content
        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8")
            except UnicodeDecodeError:
                content = content.decode("latin-1")

        # Strip HTML tags for plain text
        try:
            root = lxml_html.fromstring(content)
            text = root.text_content() or ""
        except Exception:
            text = content or ""

        # Save to output
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"page_{page_index + 1:04d}_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
