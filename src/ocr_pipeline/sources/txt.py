"""Plain-text document source.

Treats the entire file as a single logical page.  Encoding is detected
automatically via ``charset-normalizer``.
"""

from __future__ import annotations

from pathlib import Path


from .base import DocumentSource


class TxtSource(DocumentSource):
    """Document source for plain-text files (``.txt``, ``.md``, etc.).

    A single text file is always a 1-page document.  Text extraction
    returns the file contents; rendering is not supported.
    """

    _text_cache: str | None = None

    @property
    def source_format(self) -> str:
        return "txt"

    @property
    def source_mimetype(self) -> str:
        return "text/plain"

    @property
    def page_count(self) -> int:
        return 1

    def _read_text(self) -> str:
        """Detect encoding and read the file, caching the result."""
        if self._text_cache is not None:
            return self._text_cache

        try:
            from charset_normalizer import from_path

            results = from_path(str(self.path))
            if results:
                self._text_cache = str(results.best())
            else:
                # Fallback to utf-8
                self._text_cache = self.path.read_text(encoding="utf-8")
        except Exception:
            self._text_cache = self.path.read_text(encoding="utf-8")
        return self._text_cache

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError(
            "TxtSource.render_page not supported — plain text has no visual pages."
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text = self._read_text()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
