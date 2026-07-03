"""MARC (MAchine-Readable Cataloging) document source.

Parses MARC21 binary and XML records using ``pymarc``.
Each record becomes a single logical page with bibliographic metadata.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class MarcSource(DocumentSource):
    """Document source for MARC bibliographic records (``.mrc``, ``.xml``).

    Extracts bibliographic metadata from MARC21 fields.
    MARCXML files are parsed as multi-record documents.
    """

    has_native_metadata: bool = True

    _records: list[dict] | None = None

    @property
    def source_format(self) -> str:
        return "marc"

    @property
    def source_mimetype(self) -> str:
        return "application/marc"

    @property
    def page_count(self) -> int:
        return max(len(self._load_records()), 1)

    def _load_records(self) -> list[dict]:
        if self._records is not None:
            return self._records

        from pymarc import MARCReader, parse_xml_to_array

        ext = self.path.suffix.lower()
        records: list[dict] = []

        try:
            if ext == ".xml":
                marc_records = parse_xml_to_array(str(self.path))
            else:
                with open(str(self.path), "rb") as f:
                    marc_records = list(MARCReader(f, to_unicode=True))

            for rec in marc_records:
                try:
                    r: dict = {
                        "title": rec.title() or "",
                        "author": rec.author() or "",
                        "isbn": rec.isbn() or "",
                        "publisher": rec.publisher() or "",
                        "pubyear": rec.pubyear() or "",
                        "subjects": [
                            s.strip() for s in (rec.subjects() or "").split("--") if s.strip()
                        ],
                        "physical": rec.physicaldescription() or "",
                        "notes": "",
                    }
                    # LCCN
                    lccn = rec.get("010")
                    if lccn:
                        r["lccn"] = lccn.value()
                    # Notes
                    notes = []
                    for field in rec.get_fields("500", "504", "520"):
                        val = field.value()
                        if val:
                            notes.append(val)
                    if notes:
                        r["notes"] = "; ".join(notes)
                    records.append(r)
                except Exception as exc:
                    logger.debug("MARC record parse skipped: %s", exc)
        except Exception as exc:
            logger.warning("MARC parsing failed for %s: %s", self.path.name, exc)

        self._records = records
        return records

    def extract_metadata(self) -> MetadataResult:
        records = self._load_records()
        if not records:
            return MetadataResult(
                extraction_method="marc-parsing",
                source_info=SourceInfo(format="marc", page_count=0),
            )

        r = records[0]
        return MetadataResult(
            title=r.get("title", ""),
            authors=[r["author"]] if r.get("author") else [],
            publisher=r.get("publisher", ""),
            date=r.get("pubyear", ""),
            isbn=r.get("isbn", ""),
            document_type="bibliographic-record",
            extraction_method="marc-parsing",
            keywords=r.get("subjects", []),
            source_info=SourceInfo(
                format="marc",
                page_count=len(records),
                mimetype="application/marc",
                extra={
                    "record_count": len(records),
                    "lccn": r.get("lccn", ""),
                    "physical_description": r.get("physical", ""),
                },
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("MarcSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        records = self._load_records()
        if page_index < 0 or page_index >= len(records):
            return "", None

        r = records[page_index]
        lines = [
            f"Title: {r.get('title', '')}",
            f"Author: {r.get('author', '')}",
            f"ISBN: {r.get('isbn', '')}",
            f"Publisher: {r.get('publisher', '')}, {r.get('pubyear', '')}",
            f"LCCN: {r.get('lccn', '')}",
            f"Subjects: {', '.join(r.get('subjects', []))}",
            f"Physical: {r.get('physical', '')}",
        ]
        if r.get("notes"):
            lines.append(f"Notes: {r['notes']}")
        text = "\n".join(lines)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"page_{page_index + 1:04d}_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
