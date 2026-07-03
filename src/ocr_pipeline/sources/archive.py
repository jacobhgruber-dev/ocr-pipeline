"""Archive document source — compressed file containers.

Handles ZIP, TAR, GZ, and 7z archives.  Lists contained files as
extractable text and optionally recurses into the contents.
"""

from __future__ import annotations

import logging
import tarfile
from pathlib import Path
from zipfile import ZipFile

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class ArchiveSource(DocumentSource):
    """Document source for archive files (``.zip``, ``.tar``, ``.gz``, ``.7z``).

    Lists contained files and extracts text from text files within the
    archive.  Archives with recognizable documents (PDF, DOCX, etc.)
    are listed with their paths for downstream processing.
    """

    _file_list: list[str] | None = None
    _text_contents: dict[str, str] | None = None

    @property
    def source_format(self) -> str:
        ext = self.path.suffix.lower()
        if ext in (".gz", ".bz2", ".xz"):
            return "compressed-single"
        ext_map = {".zip": "zip", ".tar": "tar", ".7z": "7z", ".tgz": "tar"}
        return ext_map.get(ext, "archive")

    @property
    def source_mimetype(self) -> str:
        ext = self.path.suffix.lower()
        mimes = {
            ".zip": "application/zip",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
            ".7z": "application/x-7z-compressed",
            ".tgz": "application/gzip",
        }
        return mimes.get(ext, "application/octet-stream")

    @property
    def page_count(self) -> int:
        return 1

    def _list_files(self) -> list[str]:
        if self._file_list is not None:
            return self._file_list

        files: list[str] = []
        ext = self.path.suffix.lower()

        if ext == ".zip":
            with ZipFile(str(self.path), "r") as zf:
                files = sorted(zf.namelist())
        elif ext in (".tar", ".tgz"):
            with tarfile.open(str(self.path), "r:*") as tf:
                files = sorted(m.name for m in tf.getmembers() if m.isfile())
        elif ext == ".7z":
            try:
                import py7zr

                with py7zr.SevenZipFile(str(self.path), "r") as szf:
                    files = sorted(szf.getnames())
            except ImportError:
                files = ["(py7zr not installed — cannot list 7z contents)"]
        elif ext in (".gz", ".bz2", ".xz"):
            # Single compressed file — don't list, just note
            stem = self.path.stem
            files = [f"Compressed file: {stem}"]
        else:
            files = [f"Unknown archive format: {ext}"]

        self._file_list = files
        return files

    def extract_metadata(self) -> MetadataResult:
        files = self._list_files()
        st = self.path.stat()

        return MetadataResult(
            title=self.path.name,
            document_type="archive",
            extraction_method="archive-listing",
            source_info=SourceInfo(
                format=self.source_format,
                page_count=1,
                mimetype=self.source_mimetype,
                extra={
                    "file_count": len(files),
                    "file_size_bytes": st.st_size,
                },
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("ArchiveSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        files = self._list_files()

        lines = [f"# Archive: {self.path.name}", ""]
        lines.append(f"Format: {self.source_format}")
        lines.append(f"Files: {len(files)}")
        lines.append("")
        lines.append("## Contents")
        lines.append("")
        for f in files[:500]:  # Cap at 500 entries
            lines.append(f"- {f}")
        if len(files) > 500:
            lines.append(f"- ... and {len(files) - 500} more files")

        # Try to extract text from common text files
        common_names = {"readme", "readme.md", "readme.txt", "index.html", "manifest.json"}
        for name in common_names:
            matched = [
                f
                for f in files
                if f.lower().endswith(name) or f.lower().split("/")[-1] == name
                if ".." not in f and not f.startswith("/")  # Reject traversal paths
            ]
            if matched:
                lines.append("")
                lines.append(f"## {matched[0]}")
                try:
                    ext = self.path.suffix.lower()
                    if ext == ".zip":
                        with ZipFile(str(self.path), "r") as zf:
                            raw = zf.read(matched[0]).decode("utf-8", errors="replace")
                            lines.append("")
                            lines.append(raw[:3000])
                    elif ext in (".tar", ".tgz"):
                        with tarfile.open(str(self.path), "r:*") as tf:
                            m = tf.getmember(matched[0])
                            fobj = tf.extractfile(m)
                            if fobj:
                                raw = fobj.read().decode("utf-8", errors="replace")
                                lines.append("")
                                lines.append(raw[:3000])
                except Exception:
                    lines.append("(could not extract text)")
                break

        text = "\n".join(lines)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
