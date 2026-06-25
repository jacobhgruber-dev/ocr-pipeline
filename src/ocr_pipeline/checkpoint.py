"""Checkpoint management for the OCR pipeline — v2 (path-keyed).

Keys on ``(relative_path, size_bytes, mtime_epoch)`` via ``FileIdentity``
instead of SHA256.  SHA256 is metadata that is updated lazily when available.

Atomic saves: writes to a ``.tmp`` file, then ``os.replace`` to the target.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import CheckpointError
from .models import (
    FileIdentity,
    PageResult,
    PageStatus,
    PdfProgress,
)

_CHECKPOINT_VERSION = 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckpointManager:
    """Read/write the OCR checkpoint file (v2 — path-keyed) with atomic saves.

    The on-disk JSON format uses ``relative_path`` as the key inside the
    ``"pdfs"`` object.  Each value is the serialized ``PdfProgress``.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, PdfProgress]:
        """Load the checkpoint from disk.

        Returns:
            Dict mapping ``relative_path`` → ``PdfProgress``.  Empty dict
            if the file does not exist or cannot be parsed.
        """
        if not self._path.exists():
            return {}

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CheckpointError(f"Failed to parse checkpoint file: {self._path}") from exc

        pdfs: dict[str, PdfProgress] = {}
        for rel_path, entry in raw.get("pdfs", {}).items():
            try:
                pdfs[rel_path] = PdfProgress.from_dict(entry)
            except (KeyError, TypeError, ValueError) as exc:
                raise CheckpointError(
                    f"Corrupt entry in checkpoint for relative_path={rel_path}"
                ) from exc

        return pdfs

    def save(self, pdfs: dict[str, PdfProgress]) -> None:
        """Atomically write the checkpoint to disk.

        Writes to a temporary file first, then atomically replaces the
        target path via ``os.replace``.
        """
        existing_started_at: str | None = None
        if self._path.exists():
            try:
                existing = json.loads(self._path.read_text(encoding="utf-8"))
                existing_started_at = existing.get("started_at")
            except (json.JSONDecodeError, OSError):
                pass

        payload: dict[str, Any] = {
            "version": _CHECKPOINT_VERSION,
            "started_at": existing_started_at or _now_iso(),
            "updated_at": _now_iso(),
            "pdfs": {rel_path: p.to_dict() for rel_path, p in pdfs.items()},
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self._path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(tmp_path, self._path)
        except OSError as exc:
            raise CheckpointError(f"Failed to write checkpoint: {self._path}") from exc

    def get_or_create(
        self,
        file_id: FileIdentity,
        page_count: int,
        has_extractable_text: bool,
        metadata: dict[str, Any] | None = None,
    ) -> PdfProgress:
        """Return existing ``PdfProgress`` or create a new one with PENDING pages.

        Args:
            file_id: Identity of the PDF file (path, size, mtime, optional sha256).
            page_count: Total number of pages in the PDF.
            has_extractable_text: Whether text is extractable via PyMuPDF fast path.
            metadata: Arbitrary metadata to store with the progress entry
                      (e.g. tags, source info, etc.).

        Returns:
            Existing or newly created ``PdfProgress`` instance.
        """
        pdfs = self.load()
        rel_path = file_id.relative_path

        if rel_path in pdfs:
            # Update sha256 metadata lazily if now available.
            existing = pdfs[rel_path]
            if file_id.sha256 and (
                not hasattr(existing, "file_identity")
                or existing.file_identity.sha256 != file_id.sha256  # type: ignore[union-attr]
            ):
                existing.file_identity.sha256 = file_id.sha256  # type: ignore[union-attr]
                self.save(pdfs)
            return existing

        pp = PdfProgress(
            sha256=file_id.sha256 or "",
            short_sha=file_id.sha256[:12] if file_id.sha256 else "",
            path=file_id.relative_path,
            filename=Path(file_id.relative_path).name,
            file_identity=file_id,
            page_count=page_count,
            has_extractable_text=has_extractable_text,
            metadata=metadata or {},
            pages=[
                PageResult(
                    sha256=file_id.sha256 or "",
                    page_index=i,
                    page_label=f"page_{i + 1:04d}",
                    has_extractable_text=has_extractable_text,
                )
                for i in range(page_count)
            ],
        )
        pdfs[rel_path] = pp
        self.save(pdfs)
        return pp

    def update_page(self, relative_path: str, page: PageResult) -> None:
        """Update a single page in the checkpoint and persist.

        Raises:
            CheckpointError: If *relative_path* is not found.
            CheckpointError: If *page.page_index* is out of range.
        """
        pdfs = self.load()
        if relative_path not in pdfs:
            raise CheckpointError(
                f"Cannot update page for unknown PDF: relative_path={relative_path}"
            )

        pp = pdfs[relative_path]
        if page.page_index < 0 or page.page_index >= len(pp.pages):
            raise CheckpointError(
                f"Page index {page.page_index} out of range "
                f"(0–{len(pp.pages) - 1}) for relative_path={relative_path}"
            )

        pp.pages[page.page_index] = page
        self.save(pdfs)

    def stats(self) -> dict[str, int | float]:
        """Return aggregate statistics across all PDFs in the checkpoint."""
        pdfs = self.load()
        total_pdfs = len(pdfs)
        total_pages = 0
        complete = 0
        failed = 0
        pending = 0
        running = 0
        estimated_cost = 0.0

        for pp in pdfs.values():
            total_pages += pp.page_count
            for page in pp.pages:
                estimated_cost += page.estimated_cost
                if page.status in (PageStatus.COMPLETE, PageStatus.EXTRACTED):
                    complete += 1
                elif page.status == PageStatus.FAILED:
                    failed += 1
                elif page.status == PageStatus.PENDING:
                    pending += 1
                elif page.status in (
                    PageStatus.RENDERED,
                    PageStatus.OCR_RUNNING,
                    PageStatus.MERGING,
                ):
                    running += 1

        return {
            "total_pdfs": total_pdfs,
            "total_pages": total_pages,
            "complete": complete,
            "failed": failed,
            "pending": pending,
            "running": running,
            "estimated_cost": round(estimated_cost, 4),
        }

    def completed_pages(self, relative_path: str) -> set[int]:
        """Return the set of 0-based page indices that are COMPLETE or EXTRACTED."""
        pdfs = self.load()
        pp = pdfs.get(relative_path)
        if pp is None:
            return set()
        return {
            p.page_index
            for p in pp.pages
            if p.status in (PageStatus.COMPLETE, PageStatus.EXTRACTED)
        }

    # ------------------------------------------------------------------
    # new v2 methods
    # ------------------------------------------------------------------

    def is_file_unchanged(self, file_id: FileIdentity) -> bool:
        """Check whether a file matches the existing checkpoint entry.

        Returns ``True`` if the checkpoint has an entry for
        ``file_id.relative_path`` and the stored identity has the same
        ``size_bytes`` and ``mtime_epoch``.  Returns ``False`` if the file
        is new, has changed, or the checkpoint entry does not exist.
        """
        pdfs = self.load()
        pp = pdfs.get(file_id.relative_path)
        if pp is None:
            return False
        if pp.file_identity is None:
            return False
        existing = pp.file_identity
        return (
            existing.size_bytes == file_id.size_bytes
            and existing.mtime_epoch == file_id.mtime_epoch
        )

    def invalidate_file(self, relative_path: str) -> None:
        """Mark all pages of a file as PENDING so they will be re-processed.

        Does nothing if the file is not in the checkpoint.
        """
        pdfs = self.load()
        pp = pdfs.get(relative_path)
        if pp is None:
            return
        for page in pp.pages:
            page.status = PageStatus.PENDING
            page.error = None
        self.save(pdfs)

    # ------------------------------------------------------------------
    # migration
    # ------------------------------------------------------------------

    @staticmethod
    def migrate_from_v1(old_checkpoint_path: Path, input_dir: Path) -> int:
        """Migrate a v1 (SHA256-keyed) checkpoint to v2 (path-keyed) format.

        Reads the old checkpoint, scans ``input_dir`` to find each file by
        its stored ``path`` field, computes ``size_bytes`` and
        ``mtime_epoch``, and writes a new v2 checkpoint alongside the old
        one (same directory, ``.v2.json`` suffix).

        Args:
            old_checkpoint_path: Path to the v1 checkpoint JSON file.
            input_dir: Root directory containing the PDF files referenced
                       by ``path`` fields in the old checkpoint.

        Returns:
            Number of PDF entries migrated.
        """
        if not old_checkpoint_path.exists():
            raise CheckpointError(f"v1 checkpoint not found: {old_checkpoint_path}")

        try:
            raw = json.loads(old_checkpoint_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CheckpointError(f"Failed to parse v1 checkpoint: {old_checkpoint_path}") from exc

        # Build a lookup: relative_path → (size, mtime) for all files under input_dir.
        path_to_stat: dict[str, tuple[int, float]] = {}
        for pdf_path in input_dir.rglob("*.pdf"):
            try:
                rel = str(pdf_path.relative_to(input_dir))
                st = pdf_path.stat()
                path_to_stat[rel] = (st.st_size, st.st_mtime)
            except OSError:
                continue

        new_pdfs: dict[str, PdfProgress] = {}
        migrated = 0

        for old_sha256, entry in raw.get("pdfs", {}).items():
            old_path = entry.get("path", "")
            if not old_path:
                continue

            # Try to find a matching file by relative path.
            stat_info = path_to_stat.get(old_path)
            if stat_info is None:
                # Try case-insensitive match as a fallback.
                for candidate, st in path_to_stat.items():
                    if candidate.lower() == old_path.lower():
                        stat_info = (st.st_size, st.st_mtime)
                        old_path = candidate  # use canonical casing
                        break

            if stat_info is None:
                continue  # file not found in input_dir — skip

            size_bytes, mtime_epoch = stat_info

            file_id = FileIdentity(
                relative_path=old_path,
                size_bytes=size_bytes,
                mtime_epoch=mtime_epoch,
                sha256=old_sha256,
            )

            # Build PdfProgress from the old entry, adapting fields.
            try:
                pp = PdfProgress.from_dict(entry)
            except (KeyError, TypeError, ValueError):
                continue  # skip corrupt entries

            # Overwrite the file_identity with our newly computed one.
            pp.file_identity = file_id  # type: ignore[union-attr]

            new_pdfs[old_path] = pp
            migrated += 1

        # Write the new checkpoint.
        new_path = old_checkpoint_path.with_suffix(".v2.json")
        payload: dict[str, Any] = {
            "version": _CHECKPOINT_VERSION,
            "started_at": raw.get("started_at", _now_iso()),
            "updated_at": _now_iso(),
            "pdfs": {rel_path: p.to_dict() for rel_path, p in new_pdfs.items()},
        }

        new_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = new_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(tmp_path, new_path)
        except OSError as exc:
            raise CheckpointError(f"Failed to write migrated checkpoint: {new_path}") from exc

        return migrated
