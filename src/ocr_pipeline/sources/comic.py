"""Comic book archive source — CBZ and CBR files.

CBZ = ZIP archive of images.  CBR = RAR archive of images.
Each image in the archive is a logical page — rendered directly
to PNG for OCR processing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from zipfile import ZipFile

from ocr_pipeline.errors import RenderError
from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}


class ComicSource(DocumentSource):
    """Document source for comic book archives (``.cbz``, ``.cbr``).

    Lists images in the archive.  Each image is a logical page rendered
    to PNG for downstream OCR processing.
    """

    has_text_extraction: bool = False

    _image_names: list[str] | None = None

    @property
    def source_format(self) -> str:
        ext = self.path.suffix.lower()
        return {"cbz": "cbz", "cbr": "cbr"}.get(ext.lstrip("."), "comic")

    @property
    def source_mimetype(self) -> str:
        ext = self.path.suffix.lower()
        return {"cbz": "application/x-cbz", "cbr": "application/x-cbr"}.get(
            ext.lstrip("."), "application/octet-stream"
        )

    def _list_images(self) -> list[str]:
        if self._image_names is not None:
            return self._image_names

        ext = self.path.suffix.lower()
        images: list[str] = []

        if ext == ".cbz":
            with ZipFile(str(self.path), "r") as zf:
                for name in sorted(zf.namelist()):
                    if Path(name).suffix.lower() in _IMAGE_EXTS:
                        images.append(name)
        elif ext == ".cbr":
            try:
                import rarfile

                with rarfile.RarFile(str(self.path), "r") as rf:
                    for info in sorted(rf.infolist(), key=lambda i: i.filename):
                        if Path(info.filename).suffix.lower() in _IMAGE_EXTS:
                            images.append(info.filename)
            except ImportError:
                logger.warning("rarfile not installed — cannot read CBR files")
                images.append("(rarfile not installed)")
            except Exception as exc:
                logger.warning("Failed to read CBR: %s", exc)

        self._image_names = images
        return images

    @property
    def page_count(self) -> int:
        return max(len(self._list_images()), 1)

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        images = self._list_images()
        if page_index < 0 or page_index >= len(images):
            raise IndexError(f"Page {page_index} out of range ({len(images)} images)")

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"page_{page_index + 1:04d}.png"

        if out_path.exists():
            return out_path

        ext = self.path.suffix.lower()
        try:
            if ext == ".cbz":
                with ZipFile(str(self.path), "r") as zf:
                    data = zf.read(images[page_index])
            elif ext == ".cbr":
                import rarfile

                with rarfile.RarFile(str(self.path), "r") as rf:
                    data = rf.read(images[page_index])
            else:
                raise ValueError(f"Unsupported comic format: {ext}")

            from PIL import Image
            from io import BytesIO

            img = Image.open(BytesIO(data))
            img.save(str(out_path), "PNG")
            return out_path
        except Exception as exc:
            raise RenderError(
                f"Failed to render comic page {page_index} from {self.path.name}: {exc}"
            ) from exc

    def extract_metadata(self) -> MetadataResult:
        images = self._list_images()
        st = self.path.stat()

        return MetadataResult(
            title=self.path.stem,
            document_type="comic",
            extraction_method="comic-archive",
            source_info=SourceInfo(
                format=self.source_format,
                page_count=len(images),
                mimetype=self.source_mimetype,
                extra={
                    "image_count": len(images),
                    "file_size_bytes": st.st_size,
                },
            ),
        )

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        # Comics have no inherent text — must go through OCR
        images = self._list_images()
        if page_index < 0 or page_index >= len(images):
            return "", None
        return f"[Comic page {page_index + 1}: {images[page_index]}]", None
