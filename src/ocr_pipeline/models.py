"""Core dataclass models for the OCR pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def now_iso() -> str:
    """Current UTC time as ISO 8601 string — shared helper across the codebase."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PageStatus(str, Enum):
    """Processing status for a single PDF page."""

    PENDING = "pending"
    EXTRACTED = "extracted"  # text-extractable page done
    RENDERED = "rendered"  # PNG rendered (image-only)
    OCR_RUNNING = "ocr_running"  # engines in progress
    MERGING = "merging"  # VLM merge in progress
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"  # duplicate file


class EngineName(str, Enum):
    """Supported OCR engine identifiers."""

    GOOGLE_DOC_AI = "google_doc_ai"
    MATHPIX = "mathpix"
    MARKER = "marker"
    SURYA2 = "surya2"
    GROBID = "grobid"  # metadata extraction, not page-level OCR
    TESSERACT = "tesseract"
    TROCR = "trocr"  # handwriting recognition


# ---------------------------------------------------------------------------
# Source metadata
# ---------------------------------------------------------------------------


@dataclass
class SourceInfo:
    """Provenance and technical metadata for an ingested document.

    Captures the original format, conversion chain, and identity clues
    so downstream consumers (cataloguers, indexers, rights-review tools)
    can make informed decisions.

    Attributes:
        format: Original file format (``"pdf"``, ``"epub"``, ``"docx"``, etc.).
        page_count: Number of logical pages in the document.
        mimetype: IANA media type (e.g. ``"application/epub+zip"``).
        converted_from: When the document was auto-converted from another
            format, this holds the name of the original format.  ``None``
            for natively supported formats.
        title: Document title, if extractable from the source.
        extra: Arbitrary per-format metadata (e.g. Word document revision
            history, EPUB spine order).
    """

    format: str = ""
    page_count: int = 0
    mimetype: str = ""
    converted_from: str | None = None
    title: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "page_count": self.page_count,
            "mimetype": self.mimetype,
            "converted_from": self.converted_from,
            "title": self.title,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SourceInfo:
        return cls(
            format=str(d.get("format", "")),
            page_count=int(d.get("page_count", 0)),
            mimetype=str(d.get("mimetype", "")),
            converted_from=d.get("converted_from"),
            title=str(d.get("title", "")),
            extra=d.get("extra", {}) or {},
        )


@dataclass
class RightsInfo:
    """Copyright, licensing, and access-control metadata.

    Attributes:
        license: SPDX identifier or free-text license name
            (e.g. ``"CC-BY-4.0"``, ``"Public Domain"``).
        license_url: Canonical URL for the license text.
        rights_holder: Person or organisation that holds the copyright.
        copyright_holder: Alias for *rights_holder* (user-facing).
        access_restrictions: Human-readable description of any access
            restrictions (e.g. ``"Embargoed until 2027-01-01"``).
        open_access: Whether the document is freely available (bool as str).
        extra: Arbitrary extension fields (e.g. copyright registration
            numbers, territorial restrictions).
    """

    license: str = ""
    license_url: str = ""
    rights_holder: str = ""
    copyright_holder: str = ""
    access_restrictions: str = ""
    open_access: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "license": self.license,
            "license_url": self.license_url,
            "rights_holder": self.rights_holder,
            "copyright_holder": self.copyright_holder,
            "access_restrictions": self.access_restrictions,
            "open_access": self.open_access,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RightsInfo:
        return cls(
            license=str(d.get("license", "")),
            license_url=str(d.get("license_url", "")),
            rights_holder=str(d.get("rights_holder", "")),
            copyright_holder=str(d.get("copyright_holder", "")),
            access_restrictions=str(d.get("access_restrictions", "")),
            open_access=bool(d.get("open_access", False)),
            extra=d.get("extra", {}) or {},
        )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class WordBbox:
    """Per-word bounding box from OCR engines.

    Carries the exact pixel-position of each recognised word so that
    downstream consumers (hOCR, ALTO, searchable PDF) can use word-level
    coordinates instead of line- or block-level fallbacks.

    Attributes:
        text: The recognised word string.
        bbox: ``(x0, y0, x1, y1)`` in page coordinates, or ``None``
            when the engine did not provide a position.
        confidence: Engine-reported confidence for this word (0.0–1.0).
    """

    text: str
    bbox: tuple[float, float, float, float] | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"text": self.text, "confidence": self.confidence}
        if self.bbox:
            result["bbox"] = list(self.bbox)
        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WordBbox:
        bbox = tuple(d["bbox"]) if "bbox" in d else None
        return cls(
            text=d["text"],
            bbox=bbox,
            confidence=float(d.get("confidence", 0.0)),
        )


@dataclass
class Block:
    """A structured block of content with bounding box."""

    type: str  # "text", "table", "figure", "heading", "equation", "footer", "header"
    text: str = ""
    bbox: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1) in page coords
    confidence: float = 0.0
    children: list[Block] = field(default_factory=list)
    words: list[WordBbox] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = {"type": self.type, "text": self.text, "confidence": self.confidence}
        if self.bbox:
            result["bbox"] = list(self.bbox)
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        if self.words:
            result["words"] = [w.to_dict() for w in self.words]
        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Block:
        bbox = tuple(d["bbox"]) if "bbox" in d else None
        children = [cls.from_dict(c) for c in d.get("children", [])]
        words = [WordBbox.from_dict(w) for w in d.get("words", [])] if "words" in d else []
        return cls(
            type=d["type"],
            text=d.get("text", ""),
            bbox=bbox,
            confidence=float(d.get("confidence", 0.0)),
            children=children,
            words=words,
        )


@dataclass
class MetadataResult:
    """Structured metadata extracted from an academic document.

    Populated by GrobidEngine (or future metadata extractors) and attached
    to the PDF-level ``PdfProgress.metadata`` dict.
    """

    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    doi: str = ""
    journal: str = ""
    volume: str = ""
    issue: str = ""
    year: str = ""
    pages: str = ""
    references: list[dict] = field(default_factory=list)
    raw_tei: str = ""  # raw GROBID TEI XML for debugging

    # -- NEW: universal fields --
    document_type: str = ""  # "academic_article", "legal_opinion", "book", "technical_spec", etc.
    language: str = ""  # ISO 639-1
    publisher: str = ""  # journal, court, publishing house, company, etc.
    date: str = ""  # full date string (YYYY or YYYY-MM-DD)

    # -- NEW: type-specific fields --
    isbn: str = ""
    docket_number: str = ""
    court: str = ""
    edition: str = ""
    series: str = ""
    part_number: str = ""
    revision: str = ""

    # -- NEW: extraction metadata --
    identifiers: dict[str, str] = field(default_factory=dict)
    extraction_method: str = ""  # "vlm", "grobid", "vlm_failed", "none"
    extra: dict[str, Any] = field(default_factory=dict)

    # -- NEW: source provenance and rights --
    source_info: SourceInfo | None = None  # technical metadata about the ingested file
    rights: RightsInfo | None = None  # copyright / licensing metadata
    sha256: str = ""  # content hash of the source file

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "doi": self.doi,
            "journal": self.journal,
            "volume": self.volume,
            "issue": self.issue,
            "year": self.year,
            "pages": self.pages,
            "references": self.references,
            "raw_tei": self.raw_tei,
            # New fields
            "document_type": self.document_type,
            "language": self.language,
            "publisher": self.publisher,
            "date": self.date,
            "isbn": self.isbn,
            "docket_number": self.docket_number,
            "court": self.court,
            "edition": self.edition,
            "series": self.series,
            "part_number": self.part_number,
            "revision": self.revision,
            "identifiers": self.identifiers,
            "extraction_method": self.extraction_method,
            "extra": self.extra,
            "sha256": self.sha256,
        }
        if self.source_info is not None:
            d["source_info"] = self.source_info.to_dict()
        if self.rights is not None:
            d["rights"] = self.rights.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MetadataResult:
        source_info = None
        if "source_info" in d and d["source_info"] is not None:
            source_info = SourceInfo.from_dict(d["source_info"])
        rights = None
        if "rights" in d and d["rights"] is not None:
            rights = RightsInfo.from_dict(d["rights"])

        return cls(
            title=str(d.get("title", "")),
            authors=[str(a) for a in d.get("authors", [])],
            abstract=str(d.get("abstract", "")),
            keywords=[str(k) for k in d.get("keywords", [])],
            doi=str(d.get("doi", "")),
            journal=str(d.get("journal", "")),
            volume=str(d.get("volume", "")),
            issue=str(d.get("issue", "")),
            year=str(d.get("year", "")),
            pages=str(d.get("pages", "")),
            references=[dict(r) for r in d.get("references", [])] if d.get("references") else [],
            raw_tei=str(d.get("raw_tei", "")),
            # New fields (backward-compatible with old checkpoint files)
            document_type=str(d.get("document_type", "")),
            language=str(d.get("language", "")),
            publisher=str(d.get("publisher", "")),
            date=str(d.get("date", "")),
            isbn=str(d.get("isbn", "")),
            docket_number=str(d.get("docket_number", "")),
            court=str(d.get("court", "")),
            edition=str(d.get("edition", "")),
            series=str(d.get("series", "")),
            part_number=str(d.get("part_number", "")),
            revision=str(d.get("revision", "")),
            identifiers=d.get("identifiers", {}) or {},
            extraction_method=str(d.get("extraction_method", "")),
            extra=d.get("extra", {}) or {},
            source_info=source_info,
            rights=rights,
            sha256=str(d.get("sha256", "")),
        )


@dataclass
class EngineOutput:
    """Result from a single OCR engine invocation on a single page."""

    engine: str  # one of EngineName values (stored as str for protocol compat)
    text: str = ""  # OCR text (empty on failure)
    error: str | None = None
    duration_sec: float = 0.0
    retries: int = 0
    blocks: list[Block] | None = None  # structured blocks with bounding boxes
    confidence: float | None = None  # engine-level confidence (e.g. from surya2)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "engine": self.engine,
            "text": self.text,
            "error": self.error,
            "duration_sec": self.duration_sec,
            "retries": self.retries,
        }
        if self.blocks is not None:
            result["blocks"] = [b.to_dict() for b in self.blocks]
        if self.confidence is not None:
            result["confidence"] = self.confidence
        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EngineOutput:
        blocks = None
        if "blocks" in d and d["blocks"] is not None:
            blocks = [Block.from_dict(b) for b in d["blocks"]]
        return cls(
            engine=d["engine"],
            text=d.get("text", ""),
            error=d.get("error"),
            duration_sec=float(d.get("duration_sec", 0.0)),
            retries=int(d.get("retries", 0)),
            blocks=blocks,
            confidence=d.get("confidence"),
        )


@dataclass
class FileIdentity:
    """Stable identity for a file, independent of SHA256 changes.

    Used as the primary checkpoint key so that reorganized or re-downloaded
    files (which change SHA256) can still be matched.

    *file_type* is added in v0.3 so the checkpoint layer can distinguish
    PDF from non-PDF sources without inspecting files on disk.  Defaults
    to ``"pdf"`` for backward compatibility with v0.2 checkpoints.
    """

    relative_path: str  # e.g. "Pope Paul VI/1964/issue_1.pdf"
    size_bytes: int
    mtime_epoch: float
    sha256: str | None = None  # populated lazily after hashing
    file_type: str = "pdf"  # e.g. "pdf", "epub", "docx", "png"

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "mtime_epoch": self.mtime_epoch,
            "sha256": self.sha256,
            "file_type": self.file_type,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileIdentity:
        return cls(
            relative_path=d["relative_path"],
            size_bytes=int(d["size_bytes"]),
            mtime_epoch=float(d["mtime_epoch"]),
            sha256=d.get("sha256"),
            file_type=str(d.get("file_type", "pdf")),
        )


@dataclass
class PageResult:
    """Processing result for a single page within a PDF."""

    sha256: str  # full SHA256 of the PDF
    page_index: int  # 0-based
    page_label: str  # "page_0001" style
    has_extractable_text: bool = False
    status: PageStatus = PageStatus.PENDING
    engine_outputs: dict[str, EngineOutput] = field(default_factory=dict)
    merged_markdown: str = ""
    vlm_raw_response: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    estimated_cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict.

        ``merged_markdown`` is intentionally excluded — it lives on disk at
        ``{output_dir}/{short_sha}/page_{N:04d}_final.md``.
        """
        return {
            "sha256": self.sha256,
            "page_index": self.page_index,
            "page_label": self.page_label,
            "has_extractable_text": self.has_extractable_text,
            "status": self.status.value,
            "engine_outputs": {k: v.to_dict() for k, v in self.engine_outputs.items()},
            "merged_markdown": "",  # not stored in checkpoint
            "vlm_raw_response": self.vlm_raw_response,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "estimated_cost": self.estimated_cost,
            "metadata": self.metadata,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PageResult:
        engine_outputs: dict[str, EngineOutput] = {}
        for key, val in d.get("engine_outputs", {}).items():
            engine_outputs[key] = EngineOutput.from_dict(val)

        return cls(
            sha256=d["sha256"],
            page_index=int(d["page_index"]),
            page_label=d["page_label"],
            has_extractable_text=bool(d.get("has_extractable_text", False)),
            status=PageStatus(d["status"]),
            engine_outputs=engine_outputs,
            merged_markdown=d.get("merged_markdown", ""),
            vlm_raw_response=d.get("vlm_raw_response", ""),
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
            error=d.get("error"),
            estimated_cost=float(d.get("estimated_cost", 0.0)),
            metadata=d.get("metadata", {}),
            confidence=d.get("confidence"),
        )


@dataclass
class PdfProgress:
    """Processing progress for a single file in the corpus.

    Despite the name, this dataclass is now used for *any* file type
    (PDF, image, EPUB, DOCX, etc.).  The ``file_type`` field records
    the original format.  Backward-compatible: checkpoints written by
    v0.2 default to ``file_type="pdf"``.
    """

    sha256: str  # full SHA256
    short_sha: str  # first 12 chars for directory naming
    path: str  # relative path in sources/ (e.g., "Pope Paul VI/1964/...")
    filename: str
    page_count: int
    has_extractable_text: bool
    pages: list[PageResult] = field(default_factory=list)
    file_identity: FileIdentity | None = None  # populated by checkpoint manager
    metadata: dict[str, Any] = field(default_factory=dict)
    file_type: str = "pdf"  # e.g. "pdf", "epub", "docx", "png"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "sha256": self.sha256,
            "short_sha": self.short_sha,
            "path": self.path,
            "filename": self.filename,
            "page_count": self.page_count,
            "has_extractable_text": self.has_extractable_text,
            "pages": [p.to_dict() for p in self.pages],
            "metadata": self.metadata,
            "file_type": self.file_type,
        }
        if self.file_identity is not None:
            result["file_identity"] = self.file_identity.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PdfProgress:
        file_identity = None
        if "file_identity" in d:
            file_identity = FileIdentity.from_dict(d["file_identity"])

        return cls(
            sha256=d["sha256"],
            short_sha=d["short_sha"],
            path=d["path"],
            filename=d["filename"],
            page_count=int(d["page_count"]),
            has_extractable_text=bool(d["has_extractable_text"]),
            pages=[PageResult.from_dict(p) for p in d.get("pages", [])],
            file_identity=file_identity,
            metadata=d.get("metadata", {}),
            file_type=str(d.get("file_type", "pdf")),
        )
