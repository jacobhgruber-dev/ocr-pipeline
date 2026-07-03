"""Jupyter notebook source — .ipynb files with rich metadata.

Parses notebook JSON, extracts markdown + code cells, and metadata
from the notebook-level ``metadata`` dict.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class NotebookSource(DocumentSource):
    """Document source for Jupyter notebooks (``.ipynb``).

    Extracts text from markdown cells and code cells (incl. outputs).
    Notebook-level metadata provides title, authors, and kernel info.
    """

    _text_cache: str | None = None
    _meta_cache: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        return "notebook"

    @property
    def source_mimetype(self) -> str:
        return "application/x-ipynb+json"

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> tuple[str, dict[str, str]]:
        if self._text_cache is not None and self._meta_cache is not None:
            return self._text_cache, self._meta_cache

        raw = self.path.read_text(encoding="utf-8", errors="replace")
        try:
            nb = json.loads(raw)
        except json.JSONDecodeError:
            self._text_cache = raw
            self._meta_cache = {}
            return raw, {}

        meta: dict[str, str] = {}
        nb_meta = nb.get("metadata", {})

        # Kernel / language info
        kernel = nb_meta.get("kernelspec", {})
        if kernel.get("display_name"):
            meta["kernel"] = str(kernel["display_name"])
        lang = nb_meta.get("language_info", {})
        if lang.get("name"):
            meta["language"] = str(lang["name"])

        # Title from notebook metadata or first heading
        if nb_meta.get("title"):
            meta["title"] = str(nb_meta["title"])
        authors = nb_meta.get("authors", [])
        if authors and isinstance(authors, list):
            meta["author"] = ", ".join(str(a) for a in authors)

        # Extract cell content
        parts: list[str] = []
        for cell in nb.get("cells", []):
            cell_type = cell.get("cell_type", "")
            source = cell.get("source", [])

            if isinstance(source, list):
                source_text = "".join(source)
            else:
                source_text = str(source)

            if cell_type == "markdown":
                parts.append(source_text.strip())
            elif cell_type == "code":
                parts.append(f"```python\n{source_text.strip()}\n```")
                # Include text outputs
                for output in cell.get("outputs", []):
                    if output.get("output_type") == "stream":
                        out_text = "".join(output.get("text", []))
                        if out_text.strip():
                            parts.append(f"```\n{out_text.strip()}\n```")
                    elif output.get("output_type") == "execute_result":
                        data = output.get("data", {})
                        text_plain = data.get("text/plain", [])
                        if text_plain:
                            parts.append("".join(text_plain))
            elif cell_type == "raw":
                parts.append(source_text)

        self._text_cache = "\n\n".join(p for p in parts if p)
        self._meta_cache = meta
        return self._text_cache, meta

    def extract_metadata(self) -> MetadataResult:
        _text, meta = self._parse()
        st = self.path.stat()

        return MetadataResult(
            title=meta.get("title", ""),
            authors=[meta["author"]] if "author" in meta else [],
            language=meta.get("language", ""),
            document_type="notebook",
            extraction_method="notebook-parsing",
            source_info=SourceInfo(
                format="notebook",
                page_count=1,
                mimetype="application/x-ipynb+json",
                extra={
                    "kernel": meta.get("kernel", ""),
                    "file_size_bytes": st.st_size,
                },
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("NotebookSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        text, _meta = self._parse()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
