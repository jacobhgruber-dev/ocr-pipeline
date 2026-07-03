"""Checkpoint management for the OCR pipeline — v3 (per-PDF files).

Each PDF gets its own checkpoint file under ``base_dir/{short_sha}.json``
instead of a monolithic file.  This eliminates O(n²) I/O on large batches
by scoping reads/writes to individual PDFs.

Atomic saves: writes to a ``.tmp`` file, then ``os.replace`` to the target.
"""

from __future__ import annotations

import hashlib
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

_CHECKPOINT_VERSION = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckpointManager:
    """Read/write per-PDF checkpoint files with atomic saves (v3).

    Each PDF is stored as ``{sha256_short}.json`` under *base_dir*.
    This scopes reads and writes to individual PDFs — a 500-page PDF
    only reads and writes its own file, not the entire corpus.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _pdf_path(self, rel_path: str) -> Path:
        """Map a relative path to a stable filename under base_dir."""
        h = hashlib.sha256(rel_path.encode()).hexdigest()[:16]
        return self.base_dir / f"{h}.json"

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, PdfProgress]:
        """Load all PDF progress entries from per-PDF files.

        Iterates all ``.json`` files under *base_dir*, parses each,
        and returns a dict keyed by ``relative_path``.
        """
        if not self.base_dir.is_dir():
            return {}

        pdfs: dict[str, PdfProgress] = {}
        for json_file in sorted(self.base_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                pp = PdfProgress.from_dict(data["pdf"])
                pdfs[pp.path] = pp
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue  # skip corrupt / in-progress files

        return pdfs

    def save(self, pdfs: dict[str, PdfProgress]) -> None:
        """Write each PDF progress to its own file.

        Each entry is written to ``_pdf_path(rel_path)`` atomically.
        """
        started_at = _now_iso()
        for rel_path, pp in pdfs.items():
            fp = self._pdf_path(rel_path)
            payload: dict[str, Any] = {
                "version": _CHECKPOINT_VERSION,
                "started_at": started_at,
                "updated_at": _now_iso(),
                "rel_path": rel_path,
                "pdf": pp.to_dict(),
            }
            tmp_path: Path = fp.with_suffix(".tmp")
            try:
                tmp_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                os.replace(str(tmp_path), str(fp))
            except OSError as exc:
                raise CheckpointError(f"Failed to write checkpoint: {fp}") from exc

    def get_or_create(
        self,
        file_id: FileIdentity,
        page_count: int,
        has_extractable_text: bool,
        metadata: dict[str, Any] | None = None,
    ) -> PdfProgress:
        """Return existing ``PdfProgress`` or create a new one with PENDING pages."""
        rel_path = file_id.relative_path
        fp = self._pdf_path(rel_path)

        if fp.exists():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                existing = PdfProgress.from_dict(data["pdf"])
                # Update sha256 lazily if now available
                if file_id.sha256 and (
                    not hasattr(existing, "file_identity")
                    or existing.file_identity is None
                    or existing.file_identity.sha256 != file_id.sha256
                ):
                    if existing.file_identity is not None:
                        existing.file_identity.sha256 = file_id.sha256
                    existing.sha256 = file_id.sha256
                    self.save({rel_path: existing})
                return existing
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass  # fall through to create new

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
        self.save({rel_path: pp})
        return pp

    def update_page(self, relative_path: str, page: PageResult) -> None:
        """Update a single page and atomically persist only its PDF's file.

        Raises:
            CheckpointError: If *relative_path* is not found or the page
                             index is out of range.
        """
        fp = self._pdf_path(relative_path)
        if not fp.exists():
            raise CheckpointError(
                f"Cannot update page for unknown PDF: relative_path={relative_path}"
            )

        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            pp = PdfProgress.from_dict(data["pdf"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise CheckpointError(
                f"Corrupt checkpoint file for relative_path={relative_path}"
            ) from exc

        if page.page_index < 0 or page.page_index >= len(pp.pages):
            raise CheckpointError(
                f"Page index {page.page_index} out of range "
                f"(0–{len(pp.pages) - 1}) for relative_path={relative_path}"
            )

        pp.pages[page.page_index] = page

        payload: dict[str, Any] = {
            "version": _CHECKPOINT_VERSION,
            "started_at": data.get("started_at", _now_iso()),
            "updated_at": _now_iso(),
            "rel_path": relative_path,
            "pdf": pp.to_dict(),
        }
        tmp_path: Path = fp.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(str(tmp_path), str(fp))
        except OSError as exc:
            raise CheckpointError(f"Failed to write checkpoint: {fp}") from exc

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
        fp = self._pdf_path(relative_path)
        if not fp.exists():
            return set()
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            pp = PdfProgress.from_dict(data["pdf"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return set()
        return {
            p.page_index
            for p in pp.pages
            if p.status in (PageStatus.COMPLETE, PageStatus.EXTRACTED)
        }

    # ------------------------------------------------------------------
    # v3 methods
    # ------------------------------------------------------------------

    def is_file_unchanged(self, file_id: FileIdentity) -> bool:
        """Check whether a file matches the existing checkpoint entry."""
        fp = self._pdf_path(file_id.relative_path)
        if not fp.exists():
            return False
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            pp = PdfProgress.from_dict(data["pdf"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return False
        if pp.file_identity is None:
            return False
        existing = pp.file_identity
        return (
            existing.size_bytes == file_id.size_bytes
            and existing.mtime_epoch == file_id.mtime_epoch
        )

    def invalidate_file(self, relative_path: str) -> None:
        """Mark all pages of a file as PENDING so they will be re-processed."""
        fp = self._pdf_path(relative_path)
        if not fp.exists():
            return
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            pp = PdfProgress.from_dict(data["pdf"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return
        for page in pp.pages:
            page.status = PageStatus.PENDING
            page.error = None
        self.save({relative_path: pp})

    # ------------------------------------------------------------------
    # migration
    # ------------------------------------------------------------------

    @staticmethod
    def migrate_from_v1(old_checkpoint_path: Path, input_dir: Path) -> int:
        """Migrate a v1 (SHA256-keyed) checkpoint to v2 (path-keyed) format."""
        if not old_checkpoint_path.exists():
            raise CheckpointError(f"v1 checkpoint not found: {old_checkpoint_path}")

        try:
            raw = json.loads(old_checkpoint_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CheckpointError(f"Failed to parse v1 checkpoint: {old_checkpoint_path}") from exc

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

            stat_info = path_to_stat.get(old_path)
            if stat_info is None:
                for candidate, stat_tuple in path_to_stat.items():
                    if candidate.lower() == old_path.lower():
                        stat_info = stat_tuple
                        old_path = candidate
                        break

            if stat_info is None:
                continue

            size_bytes, mtime_epoch = stat_info

            file_id = FileIdentity(
                relative_path=old_path,
                size_bytes=size_bytes,
                mtime_epoch=mtime_epoch,
                sha256=old_sha256,
            )

            try:
                pp = PdfProgress.from_dict(entry)
            except (KeyError, TypeError, ValueError):
                continue

            pp.file_identity = file_id  # type: ignore[union-attr]

            new_pdfs[old_path] = pp
            migrated += 1

        new_path = old_checkpoint_path.with_suffix(".v2.json")
        payload: dict[str, Any] = {
            "version": _CHECKPOINT_VERSION,
            "started_at": raw.get("started_at", _now_iso()),
            "updated_at": _now_iso(),
            "pdfs": {rel_path: p.to_dict() for rel_path, p in new_pdfs.items()},
        }

        new_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path = new_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(str(tmp_path), str(new_path))
        except OSError as exc:
            raise CheckpointError(f"Failed to write migrated checkpoint: {new_path}") from exc

        return migrated
