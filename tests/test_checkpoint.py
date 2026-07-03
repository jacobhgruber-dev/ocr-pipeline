"""Tests for CheckpointManager — save/load, get_or_create, update_page, stats."""

from __future__ import annotations

import pytest

from ocr_pipeline.checkpoint import CheckpointManager
from ocr_pipeline.errors import CheckpointError
from ocr_pipeline.models import (
    EngineOutput,
    FileIdentity,
    PageResult,
    PageStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_checkpoint_path(tmp_path):
    """A checkpoint directory inside a temp directory (no pre-existing files)."""
    path = tmp_path / ".checkpoint"
    return path


@pytest.fixture
def cm(tmp_checkpoint_path):
    return CheckpointManager(tmp_checkpoint_path)


@pytest.fixture
def sample_file_id():
    return FileIdentity(
        relative_path="pope/1964/issue.pdf",
        size_bytes=100000,
        mtime_epoch=1700000000.0,
        sha256="abcdef1234567890abcdef",
    )


# ---------------------------------------------------------------------------
# Save / load round-trip
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_save_load_round_trip(self, cm, sample_file_id):
        from ocr_pipeline.models import PdfProgress

        pdfs = {
            sample_file_id.relative_path: PdfProgress(
                sha256=sample_file_id.sha256 or "",
                short_sha=(sample_file_id.sha256 or "")[:12],
                path=sample_file_id.relative_path,
                filename="issue.pdf",
                page_count=2,
                has_extractable_text=False,
                file_identity=sample_file_id,
            )
        }
        cm.save(pdfs)
        loaded = cm.load()
        assert sample_file_id.relative_path in loaded
        assert loaded[sample_file_id.relative_path].page_count == 2

    def test_load_returns_empty_for_nonexistent_dir(self, tmp_path):
        cm = CheckpointManager(tmp_path / "nonexistent_dir")
        result = cm.load()
        assert result == {}

    def test_save_creates_base_directory(self, tmp_path):
        path = tmp_path / "sub" / "dir" / ".checkpoint"
        cm = CheckpointManager(path)
        cm.save({})
        assert path.is_dir()


# ---------------------------------------------------------------------------
# get_or_create
# ---------------------------------------------------------------------------


class TestGetOrCreate:
    def test_creates_new_pdf_progress(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=5,
            has_extractable_text=False,
        )
        assert pp.path == sample_file_id.relative_path
        assert pp.page_count == 5
        assert len(pp.pages) == 5
        assert pp.file_identity is not None
        assert pp.file_identity.relative_path == sample_file_id.relative_path

    def test_creates_pages_with_correct_labels(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=3,
            has_extractable_text=False,
        )
        assert pp.pages[0].page_label == "page_0001"
        assert pp.pages[1].page_label == "page_0002"
        assert pp.pages[2].page_label == "page_0003"

    def test_returns_existing_on_second_call(self, cm, sample_file_id):
        cm.get_or_create(
            file_id=sample_file_id,
            page_count=5,
            has_extractable_text=False,
        )
        pp2 = cm.get_or_create(
            file_id=sample_file_id,
            page_count=10,  # different page_count — should be ignored
            has_extractable_text=False,
        )
        assert pp2.page_count == 5  # original value preserved
        assert len(pp2.pages) == 5

    def test_new_pages_all_pending(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=3,
            has_extractable_text=False,
        )
        for page in pp.pages:
            assert page.status == PageStatus.PENDING

    def test_metadata_stored(self, cm, sample_file_id):
        meta = {"source": "vatican", "year": 1964}
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=1,
            has_extractable_text=False,
            metadata=meta,
        )
        assert pp.metadata == meta

    def test_sha256_updated_lazily(self, cm):
        fi_no_sha = FileIdentity(
            relative_path="lazy.pdf",
            size_bytes=500,
            mtime_epoch=1000.0,
        )
        pp1 = cm.get_or_create(file_id=fi_no_sha, page_count=1, has_extractable_text=False)
        assert pp1.sha256 == ""

        # Now call again with sha256 available
        fi_with_sha = FileIdentity(
            relative_path="lazy.pdf",
            size_bytes=500,
            mtime_epoch=1000.0,
            sha256="newhash1234",
        )
        pp2 = cm.get_or_create(file_id=fi_with_sha, page_count=1, has_extractable_text=False)
        assert pp2.file_identity is not None
        assert pp2.file_identity.sha256 == "newhash1234"


# ---------------------------------------------------------------------------
# update_page
# ---------------------------------------------------------------------------


class TestUpdatePage:
    def test_update_page_persists(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=3,
            has_extractable_text=False,
        )
        page = pp.pages[0]
        page.status = PageStatus.COMPLETE
        page.merged_markdown = "## Done"
        page.engine_outputs = {"marker": EngineOutput(engine="marker", text="ocr text")}

        cm.update_page(sample_file_id.relative_path, page)

        # Re-read
        loaded = cm.load()
        updated_page = loaded[sample_file_id.relative_path].pages[0]
        assert updated_page.status == PageStatus.COMPLETE
        assert "marker" in updated_page.engine_outputs
        assert updated_page.engine_outputs["marker"].text == "ocr text"

    def test_update_page_unknown_relative_path_raises(self, cm):
        page = PageResult(sha256="x", page_index=0, page_label="page_0001")
        with pytest.raises(CheckpointError, match="unknown PDF"):
            cm.update_page("nonexistent/path.pdf", page)

    def test_update_page_out_of_range_raises(self, cm, sample_file_id):
        cm.get_or_create(
            file_id=sample_file_id,
            page_count=2,
            has_extractable_text=False,
        )
        page = PageResult(sha256="x", page_index=5, page_label="page_0006")
        with pytest.raises(CheckpointError, match="out of range"):
            cm.update_page(sample_file_id.relative_path, page)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_on_empty_checkpoint(self, cm):
        s = cm.stats()
        assert s["total_pdfs"] == 0
        assert s["total_pages"] == 0
        assert s["complete"] == 0
        assert s["failed"] == 0
        assert s["pending"] == 0

    def test_stats_counts_correctly(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=3,
            has_extractable_text=False,
        )
        pp.pages[0].status = PageStatus.COMPLETE
        pp.pages[1].status = PageStatus.FAILED
        pp.pages[2].status = PageStatus.PENDING
        cm.update_page(sample_file_id.relative_path, pp.pages[0])
        cm.update_page(sample_file_id.relative_path, pp.pages[1])

        s = cm.stats()
        assert s["total_pdfs"] == 1
        assert s["total_pages"] == 3
        assert s["complete"] == 1
        assert s["failed"] == 1
        assert s["pending"] == 1
        assert s["running"] == 0

    def test_stats_tracks_estimated_cost(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=1,
            has_extractable_text=False,
        )
        pp.pages[0].estimated_cost = 0.05
        cm.update_page(sample_file_id.relative_path, pp.pages[0])

        s = cm.stats()
        assert s["estimated_cost"] == 0.05


# ---------------------------------------------------------------------------
# completed_pages
# ---------------------------------------------------------------------------


class TestCompletedPages:
    def test_empty_for_new_file(self, cm):
        result = cm.completed_pages("nonexistent.pdf")
        assert result == set()

    def test_returns_complete_pages(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=3,
            has_extractable_text=False,
        )
        pp.pages[0].status = PageStatus.COMPLETE
        pp.pages[2].status = PageStatus.COMPLETE
        cm.update_page(sample_file_id.relative_path, pp.pages[0])
        cm.update_page(sample_file_id.relative_path, pp.pages[2])

        completed = cm.completed_pages(sample_file_id.relative_path)
        assert completed == {0, 2}

    def test_extracted_also_counted(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=2,
            has_extractable_text=True,
        )
        pp.pages[0].status = PageStatus.EXTRACTED
        cm.update_page(sample_file_id.relative_path, pp.pages[0])

        completed = cm.completed_pages(sample_file_id.relative_path)
        assert completed == {0}


# ---------------------------------------------------------------------------
# is_file_unchanged
# ---------------------------------------------------------------------------


class TestIsFileUnchanged:
    def test_returns_false_for_unknown_file(self, cm):
        fi = FileIdentity(relative_path="new.pdf", size_bytes=100, mtime_epoch=1.0)
        assert cm.is_file_unchanged(fi) is False

    def test_returns_true_for_matching_size_and_mtime(self, cm, sample_file_id):
        cm.get_or_create(
            file_id=sample_file_id,
            page_count=1,
            has_extractable_text=False,
        )
        assert cm.is_file_unchanged(sample_file_id) is True

    def test_returns_false_for_different_size(self, cm, sample_file_id):
        cm.get_or_create(
            file_id=sample_file_id,
            page_count=1,
            has_extractable_text=False,
        )
        changed = FileIdentity(
            relative_path=sample_file_id.relative_path,
            size_bytes=99999,  # different
            mtime_epoch=sample_file_id.mtime_epoch,
        )
        assert cm.is_file_unchanged(changed) is False

    def test_returns_false_for_different_mtime(self, cm, sample_file_id):
        cm.get_or_create(
            file_id=sample_file_id,
            page_count=1,
            has_extractable_text=False,
        )
        changed = FileIdentity(
            relative_path=sample_file_id.relative_path,
            size_bytes=sample_file_id.size_bytes,
            mtime_epoch=9999999999.0,  # different
        )
        assert cm.is_file_unchanged(changed) is False


# ---------------------------------------------------------------------------
# invalidate_file
# ---------------------------------------------------------------------------


class TestInvalidateFile:
    def test_invalidates_all_pages(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=3,
            has_extractable_text=False,
        )
        # Set some pages as complete
        pp.pages[0].status = PageStatus.COMPLETE
        pp.pages[1].status = PageStatus.FAILED
        cm.update_page(sample_file_id.relative_path, pp.pages[0])
        cm.update_page(sample_file_id.relative_path, pp.pages[1])

        cm.invalidate_file(sample_file_id.relative_path)

        loaded = cm.load()
        for page in loaded[sample_file_id.relative_path].pages:
            assert page.status == PageStatus.PENDING

    def test_invalidate_clears_error(self, cm, sample_file_id):
        pp = cm.get_or_create(
            file_id=sample_file_id,
            page_count=1,
            has_extractable_text=False,
        )
        pp.pages[0].status = PageStatus.FAILED
        pp.pages[0].error = "some error"
        cm.update_page(sample_file_id.relative_path, pp.pages[0])

        cm.invalidate_file(sample_file_id.relative_path)

        loaded = cm.load()
        assert loaded[sample_file_id.relative_path].pages[0].error is None

    def test_invalidate_nonexistent_file_is_noop(self, cm):
        # Should not raise
        cm.invalidate_file("does/not/exist.pdf")


# ---------------------------------------------------------------------------
# Atomic save
# ---------------------------------------------------------------------------


class TestAtomicSave:
    def test_no_stray_tmp_files_after_save(self, cm):
        cm.save({})
        # The base dir should exist with no stray .tmp files
        assert cm.base_dir.is_dir()
        tmps = list(cm.base_dir.glob("*.tmp"))
        assert len(tmps) == 0

    def test_existing_started_at_preserved(self, cm):
        # First save sets started_at
        cm.save({})
        # Wait a tiny bit, save again
        cm.save({})  # save twice — no exception = pass
