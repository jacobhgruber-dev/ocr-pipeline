"""JSON document source — structured data with JSON-LD detection.

Treats JSON files as single-page documents.  Detects JSON-LD
``@context`` blocks and extracts metadata from them.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class JsonSource(DocumentSource):
    """Document source for JSON files (``.json``, ``.jsonl``).

    Renders JSON as formatted text.  Detects schema.org JSON-LD and
    extracts title, author, date metadata where present.
    """

    _data: object | None = None

    @property
    def source_format(self) -> str:
        return "json"

    @property
    def source_mimetype(self) -> str:
        return "application/json"

    @property
    def page_count(self) -> int:
        return 1

    def _load(self) -> object:
        if self._data is not None:
            return self._data
        raw = self.path.read_text(encoding="utf-8", errors="replace")
        try:
            self._data = json.loads(raw)
        except json.JSONDecodeError:
            # Try JSONL: take first valid line
            self._data = raw
            for line in raw.splitlines():
                line = line.strip()
                if line:
                    try:
                        self._data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
        return self._data

    @staticmethod
    def _extract_json_ld(data: object) -> dict[str, str]:
        """Walk JSON-LD objects to extract common metadata fields."""
        meta: dict[str, str] = {}

        def _walk(obj: object) -> None:
            if isinstance(obj, dict):
                ctx = obj.get("@context", "")
                if ctx and ("schema.org" in str(ctx) or "jsonld" in str(ctx).lower()):
                    for key in ("name", "headline", "title"):
                        if obj.get(key):
                            meta.setdefault("title", str(obj[key]))
                    author = obj.get("author") or obj.get("creator")
                    if isinstance(author, dict):
                        meta.setdefault("author", str(author.get("name", author)))
                    elif isinstance(author, list) and author:
                        a = author[0]
                        if isinstance(a, dict):
                            meta.setdefault("author", str(a.get("name", a)))
                        elif isinstance(a, str):
                            meta.setdefault("author", a)
                    if obj.get("datePublished"):
                        meta.setdefault("date", str(obj["datePublished"]))
                    if obj.get("description"):
                        meta.setdefault("description", str(obj["description"]))
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item)

        _walk(data)
        return meta

    def extract_metadata(self) -> MetadataResult:
        data = self._load()
        meta = self._extract_json_ld(data)
        st = self.path.stat()

        return MetadataResult(
            title=meta.get("title", ""),
            authors=[meta["author"]] if "author" in meta else [],
            date=meta.get("date", ""),
            document_type="json" if "@context" not in meta else "json-ld",
            extraction_method="json-parsing",
            source_info=SourceInfo(
                format="json",
                page_count=1,
                mimetype="application/json",
                extra={
                    "file_size_bytes": st.st_size,
                },
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("JsonSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        data = self._load()
        text = json.dumps(data, indent=2, ensure_ascii=False, default=str)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
