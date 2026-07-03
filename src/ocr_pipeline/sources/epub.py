"""EPUB document source — extract text and render pages from ebooks.

Uses ``ebooklib`` to parse the EPUB, then writes each chapter/section as a
rendered HTML block.  Text extraction walks the spine reading items in order.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.errors import RenderError

from .base import DocumentSource

logger = logging.getLogger(__name__)


class EpubSource(DocumentSource):
    """Document source for EPUB 2/3 ebooks.

    Each "chapter" or spine item is treated as a logical page.  Text
    extraction strips HTML tags and returns plain text.  Rendering
    converts HTML content to PNG via a lightweight approach.
    """

    _SPINE_ITEMS: list[tuple[str, str]] | None = None  # (item_id, href)

    @property
    def source_format(self) -> str:
        return "epub"

    @property
    def source_mimetype(self) -> str:
        return "application/epub+zip"

    def _load_spine(self) -> list[tuple[str, str]]:
        """Parse the EPUB spine once and cache the ordered items."""
        if self._SPINE_ITEMS is not None:
            return self._SPINE_ITEMS

        from ebooklib import epub

        book = epub.read_epub(str(self.path))
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
        from ebooklib import epub as _epub
        from lxml import html as lxml_html

        spine = self._load_spine()
        if page_index < 0 or page_index >= len(spine):
            raise RenderError(f"EPUB page index {page_index} out of range ({len(spine)} items)")

        item_id, href = spine[page_index]
        book = _epub.read_epub(str(self.path))
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
