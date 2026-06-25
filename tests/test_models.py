"""Tests for OCR pipeline dataclass models — round-trip serialization and enums."""

from __future__ import annotations

from ocr_pipeline.models import (
    Block,
    EngineName,
    EngineOutput,
    FileIdentity,
    PageResult,
    PageStatus,
    PdfProgress,
)


# ---------------------------------------------------------------------------
# EngineName enum
# ---------------------------------------------------------------------------


class TestEngineName:
    def test_all_members_exist(self):
        expected = {"google_doc_ai", "mathpix", "marker", "surya2", "olmocr", "grobid"}
        actual = {e.value for e in EngineName}
        assert actual == expected

    def test_string_comparison(self):
        eo = EngineOutput(engine="marker", text="hello")
        assert eo.engine == EngineName.MARKER
        assert eo.engine == EngineName.MARKER.value
        assert eo.engine != EngineName.GOOGLE_DOC_AI


# ---------------------------------------------------------------------------
# PageStatus enum
# ---------------------------------------------------------------------------


class TestPageStatus:
    def test_all_values(self):
        expected = {
            "pending",
            "extracted",
            "rendered",
            "ocr_running",
            "merging",
            "complete",
            "failed",
            "skipped",
        }
        actual = {e.value for e in PageStatus}
        assert actual == expected

    def test_is_str_enum(self):
        assert isinstance(PageStatus.PENDING, str)
        assert PageStatus.PENDING == "pending"


# ---------------------------------------------------------------------------
# Block round-trip
# ---------------------------------------------------------------------------


class TestBlock:
    def test_basic_round_trip(self):
        block = Block(type="text", text="Hello world", confidence=0.99)
        d = block.to_dict()
        restored = Block.from_dict(d)
        assert restored.type == "text"
        assert restored.text == "Hello world"
        assert restored.confidence == 0.99
        assert restored.bbox is None
        assert restored.children == []

    def test_with_bbox_round_trip(self):
        block = Block(type="table", text="data", bbox=(1.0, 2.0, 3.0, 4.0))
        d = block.to_dict()
        assert d["bbox"] == [1.0, 2.0, 3.0, 4.0]
        restored = Block.from_dict(d)
        assert restored.bbox == (1.0, 2.0, 3.0, 4.0)

    def test_with_children_round_trip(self):
        child = Block(type="text", text="child")
        parent = Block(type="section", text="", children=[child])
        d = parent.to_dict()
        restored = Block.from_dict(d)
        assert len(restored.children) == 1
        assert restored.children[0].type == "text"
        assert restored.children[0].text == "child"

    def test_nested_children_round_trip(self):
        grandchild = Block(type="text", text="deep")
        child = Block(type="group", children=[grandchild])
        parent = Block(type="page", children=[child])
        d = parent.to_dict()
        restored = Block.from_dict(d)
        assert restored.children[0].children[0].text == "deep"


# ---------------------------------------------------------------------------
# EngineOutput round-trip
# ---------------------------------------------------------------------------


class TestEngineOutput:
    def test_basic_round_trip(self):
        eo = EngineOutput(engine="marker", text="OCR result", duration_sec=3.5, retries=1)
        d = eo.to_dict()
        restored = EngineOutput.from_dict(d)
        assert restored.engine == "marker"
        assert restored.text == "OCR result"
        assert restored.duration_sec == 3.5
        assert restored.retries == 1
        assert restored.error is None
        assert restored.blocks is None

    def test_with_blocks_round_trip(self):
        block = Block(type="text", text="paragraph")
        eo = EngineOutput(
            engine="google_doc_ai",
            text="text with blocks",
            blocks=[block],
        )
        d = eo.to_dict()
        restored = EngineOutput.from_dict(d)
        assert restored.blocks is not None
        assert len(restored.blocks) == 1
        assert restored.blocks[0].type == "text"

    def test_with_error_round_trip(self):
        eo = EngineOutput(engine="mathpix", error="API timeout")
        d = eo.to_dict()
        restored = EngineOutput.from_dict(d)
        assert restored.error == "API timeout"
        assert restored.text == ""


# ---------------------------------------------------------------------------
# FileIdentity round-trip
# ---------------------------------------------------------------------------


class TestFileIdentity:
    def test_round_trip(self):
        fi = FileIdentity(
            relative_path="Pope Paul VI/1964/issue_1.pdf",
            size_bytes=99999,
            mtime_epoch=1712345678.0,
            sha256="abcdef1234567890",
        )
        d = fi.to_dict()
        restored = FileIdentity.from_dict(d)
        assert restored.relative_path == fi.relative_path
        assert restored.size_bytes == fi.size_bytes
        assert restored.mtime_epoch == fi.mtime_epoch
        assert restored.sha256 == fi.sha256

    def test_without_sha256(self):
        fi = FileIdentity(
            relative_path="doc.pdf",
            size_bytes=5000,
            mtime_epoch=1000.0,
        )
        d = fi.to_dict()
        assert d["sha256"] is None
        restored = FileIdentity.from_dict(d)
        assert restored.sha256 is None


# ---------------------------------------------------------------------------
# PageResult round-trip
# ---------------------------------------------------------------------------


class TestPageResult:
    def test_basic_round_trip(self):
        pr = PageResult(sha256="abc", page_index=5, page_label="page_0006")
        d = pr.to_dict()
        restored = PageResult.from_dict(d)
        assert restored.sha256 == "abc"
        assert restored.page_index == 5
        assert restored.page_label == "page_0006"
        assert restored.status == PageStatus.PENDING

    def test_merged_markdown_excluded_from_checkpoint(self):
        pr = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            merged_markdown="## Very long markdown content",
        )
        d = pr.to_dict()
        # merged_markdown is intentionally excluded (set to empty string)
        assert d["merged_markdown"] == ""

    def test_with_engine_outputs_round_trip(self):
        eo = EngineOutput(engine="marker", text="eng text")
        pr = PageResult(
            sha256="abc",
            page_index=0,
            page_label="page_0001",
            engine_outputs={"marker": eo},
            status=PageStatus.COMPLETE,
        )
        d = pr.to_dict()
        restored = PageResult.from_dict(d)
        assert restored.status == PageStatus.COMPLETE
        assert "marker" in restored.engine_outputs
        assert restored.engine_outputs["marker"].text == "eng text"

    def test_with_all_fields_round_trip(self):
        eo = EngineOutput(engine="surya2", text="full", retries=2)
        pr = PageResult(
            sha256="deadbeef",
            page_index=42,
            page_label="page_0043",
            has_extractable_text=True,
            status=PageStatus.OCR_RUNNING,
            engine_outputs={"surya2": eo},
            vlm_raw_response='{"raw": true}',
            started_at="2024-01-01T00:00:00Z",
            completed_at="2024-01-01T01:00:00Z",
            error="some error",
            estimated_cost=0.02,
            metadata={"tags": ["theological"]},
        )
        d = pr.to_dict()
        restored = PageResult.from_dict(d)
        assert restored.has_extractable_text is True
        assert restored.status == PageStatus.OCR_RUNNING
        assert restored.vlm_raw_response == '{"raw": true}'
        assert restored.started_at == "2024-01-01T00:00:00Z"
        assert restored.completed_at == "2024-01-01T01:00:00Z"
        assert restored.error == "some error"
        assert restored.estimated_cost == 0.02
        assert restored.metadata == {"tags": ["theological"]}


# ---------------------------------------------------------------------------
# PdfProgress round-trip
# ---------------------------------------------------------------------------


class TestPdfProgress:
    def test_basic_round_trip(self):
        pp = PdfProgress(
            sha256="abc123",
            short_sha="abc123",
            path="folder/doc.pdf",
            filename="doc.pdf",
            page_count=3,
            has_extractable_text=False,
        )
        d = pp.to_dict()
        restored = PdfProgress.from_dict(d)
        assert restored.sha256 == "abc123"
        assert restored.path == "folder/doc.pdf"
        assert restored.page_count == 3
        assert restored.pages == []
        assert restored.file_identity is None

    def test_with_file_identity_round_trip(self):
        fi = FileIdentity(
            relative_path="folder/doc.pdf",
            size_bytes=1000,
            mtime_epoch=500.0,
        )
        pp = PdfProgress(
            sha256="abc",
            short_sha="abc",
            path="folder/doc.pdf",
            filename="doc.pdf",
            page_count=1,
            has_extractable_text=True,
            file_identity=fi,
        )
        d = pp.to_dict()
        assert "file_identity" in d
        restored = PdfProgress.from_dict(d)
        assert restored.file_identity is not None
        assert restored.file_identity.relative_path == "folder/doc.pdf"

    def test_with_pages_round_trip(self):
        pages = [
            PageResult(sha256="abc", page_index=0, page_label="page_0001"),
            PageResult(sha256="abc", page_index=1, page_label="page_0002"),
        ]
        pp = PdfProgress(
            sha256="abc",
            short_sha="abc",
            path="d.pdf",
            filename="d.pdf",
            page_count=2,
            has_extractable_text=False,
            pages=pages,
        )
        d = pp.to_dict()
        restored = PdfProgress.from_dict(d)
        assert len(restored.pages) == 2
        assert restored.pages[0].page_index == 0
        assert restored.pages[1].page_label == "page_0002"
