"""DJVU document source — scanned books from digital libraries.

Uses the ``djvutxt`` CLI for text extraction and ``djvudump`` for
page count.  Requires the ``djvulibre`` system package.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from ocr_pipeline.errors import RenderError
from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

_DJVUTXT = "djvutxt"
_DJVUDUMP = "djvudump"
_PAGE_RE = re.compile(r"^\s*DjVu\d+px\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+$", re.MULTILINE)


class DjvuSource(DocumentSource):
    """Document source for DJVU files (``.djvu``, ``.djv``).

    Each DJVU page is a logical page.  Text extraction uses the
    ``djvutxt`` CLI tool.  Metadata includes page dimensions.
    """

    _page_count: int | None = None

    @property
    def source_format(self) -> str:
        return "djvu"

    @property
    def source_mimetype(self) -> str:
        return "image/vnd.djvu"

    @property
    def page_count(self) -> int:
        if self._page_count is not None:
            return self._page_count
        try:
            result = subprocess.run(
                [_DJVUDUMP, str(self.path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            pages = len(_PAGE_RE.findall(result.stdout))
            self._page_count = max(pages, 1)
        except Exception:
            self._page_count = 1
        return self._page_count

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"page_{page_index + 1:04d}.png"

        if out_path.exists():
            return out_path

        try:
            # ddjvu can render DJVU pages to images
            subprocess.run(
                [
                    "ddjvu",
                    "-format=png",
                    f"-page={page_index + 1}",
                    f"-size={dpi * 8}x{dpi * 11}",
                    str(self.path),
                    str(out_path),
                ],
                capture_output=True,
                timeout=60,
                check=True,
            )
        except FileNotFoundError:
            raise NotImplementedError("ddjvu not found — install djvulibre for DJVU rendering")
        except subprocess.CalledProcessError as exc:
            raise RenderError(
                f"ddjvu failed for page {page_index} of {self.path}: {exc.stderr}"
            ) from exc

        return out_path

    def extract_metadata(self) -> MetadataResult:
        st = self.path.stat()
        return MetadataResult(
            document_type="book",
            extraction_method="djvu-cli",
            source_info=SourceInfo(
                format="djvu",
                page_count=self.page_count,
                mimetype="image/vnd.djvu",
                extra={"file_size_bytes": st.st_size},
            ),
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        if page_index < 0 or page_index >= self.page_count:
            return "", None

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"page_{page_index + 1:04d}_final.md"

        try:
            result = subprocess.run(
                [_DJVUTXT, "--page", str(page_index + 1), str(self.path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            text = result.stdout.strip()
        except FileNotFoundError:
            text = "(djvutxt not found — install djvulibre for DJVU text extraction)"
            logger.warning("djvutxt not found for %s", self.path.name)
        except Exception as exc:
            text = f"(DJVU extraction failed: {exc})"
            logger.warning("DJVU extraction failed: %s", exc)

        out_path.write_text(text, encoding="utf-8")
        return text, out_path
