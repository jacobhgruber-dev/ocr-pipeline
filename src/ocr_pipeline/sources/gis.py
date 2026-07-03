"""GIS document source — geospatial data files.

Handles GeoJSON (built-in JSON) and Shapefile (.shp via ``pyshp``).
Extracts geometry metadata, attribute tables, and coordinate reference
system information as extractable text.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult, SourceInfo

from .base import DocumentSource

logger = logging.getLogger(__name__)


class GisSource(DocumentSource):
    """Document source for geospatial files (``.geojson``, ``.shp``).

    Extracts feature metadata, attribute tables, and spatial reference
    information.  A single file is a 1-page document.
    """

    _data: dict | None = None

    @property
    def source_format(self) -> str:
        ext = self.path.suffix.lower()
        return ext.lstrip(".")

    @property
    def source_mimetype(self) -> str:
        ext = self.path.suffix.lower()
        _mimes = {
            ".geojson": "application/geo+json",
            ".shp": "application/x-shapefile",
        }
        return _mimes.get(ext, "application/octet-stream")

    @property
    def page_count(self) -> int:
        return 1

    def _parse(self) -> dict:
        if self._data is not None:
            return self._data

        ext = self.path.suffix.lower()

        if ext == ".geojson":
            raw = self.path.read_text(encoding="utf-8", errors="replace")
            try:
                geojson = json.loads(raw)
                features = geojson.get("features", [])
                self._data = {
                    "type": geojson.get("type", ""),
                    "feature_count": len(features),
                    "crs": str(geojson.get("crs", "")),
                    "geometry_types": list(
                        {f.get("geometry", {}).get("type", "Unknown") for f in features}
                    ),
                    "properties_keys": list(
                        {k for f in features for k in (f.get("properties", {}) or {})}
                    )[:50],
                }
            except json.JSONDecodeError:
                self._data = {"error": "Invalid GeoJSON"}

        elif ext == ".shp":
            try:
                import shapefile

                with shapefile.Reader(str(self.path)) as sf:
                    self._data = {
                        "type": "Shapefile",
                        "feature_count": len(sf),
                        "shape_type": str(sf.shapeType),
                        "fields": [f[0] for f in sf.fields[1:]],  # skip deletion flag
                        "bbox": list(sf.bbox),
                    }
            except ImportError:
                self._data = {"error": "pyshp not installed"}
            except Exception as exc:
                self._data = {"error": str(exc)}

        else:
            self._data = {"error": "unsupported GIS format"}

        return self._data

    def extract_metadata(self) -> MetadataResult:
        data = self._parse()
        st = self.path.stat()

        extra = {
            "feature_count": data.get("feature_count", 0),
            "geometry_types": data.get("geometry_types", []),
            "file_size_bytes": st.st_size,
        }
        if "fields" in data:
            extra["attribute_fields"] = data["fields"]
        if "bbox" in data:
            extra["bbox"] = data["bbox"]

        return MetadataResult(
            title=self.path.stem,
            document_type="gis-data",
            extraction_method="gis-parsing",
            source_info=SourceInfo(
                format=self.source_format,
                page_count=1,
                mimetype=self.source_mimetype,
                extra=extra,
            ),
        )

    def render_page(self, page_index: int, output_dir: Path, dpi: int = 300) -> Path:
        raise NotImplementedError("GisSource.render_page not supported.")

    def extract_text(
        self, page_index: int, output_dir: Path, flags: int | None = None
    ) -> tuple[str, Path | None]:
        data = self._parse()

        lines = [f"# {self.path.name}", ""]
        for key, val in data.items():
            if isinstance(val, list):
                lines.append(f"- **{key}**: {', '.join(str(v) for v in val)}")
            else:
                lines.append(f"- **{key}**: {val}")
        text = "\n".join(lines)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "page_0001_final.md"
        out_path.write_text(text, encoding="utf-8")

        return text, out_path
