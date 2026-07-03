"""Sidecar metadata reader — YAML metadata files alongside documents.

Looks for ``{filename}.meta.yaml`` next to any input file and merges
the parsed metadata into the pipeline's ``MetadataResult``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ocr_pipeline.models import MetadataResult

logger = logging.getLogger(__name__)


def load_sidecar_metadata(file_path: Path) -> dict[str, object]:
    """Load metadata from a sidecar ``.meta.yaml`` file.

    Looks for ``{file_path}.meta.yaml``.  Returns a dict of metadata
    fields that can be merged into ``MetadataResult``.

    Supported top-level keys:
        title, author, authors (list), date, language, publisher,
        document_type, edition, doi, isbn, abstract, keywords,
        license, license_url, copyright, open_access, extra (dict)

    Example sidecar file::

        title: "My Document"
        author: "Jane Researcher"
        date: "2025-06-01"
        language: "en"
        doi: "10.1234/example"
        license: "CC BY 4.0"
        license_url: "https://creativecommons.org/licenses/by/4.0/"
        extra:
          collection: "Personal Papers"
          notes: "Scanned from original"
    """
    sidecar = file_path.with_suffix(file_path.suffix + ".meta.yaml")
    if not sidecar.exists():
        # Also try .meta.yml
        sidecar = file_path.with_suffix(file_path.suffix + ".meta.yml")
        if not sidecar.exists():
            return {}

    try:
        import yaml as _yaml

        raw = sidecar.read_text(encoding="utf-8")
        data = _yaml.safe_load(raw)
        if isinstance(data, dict):
            logger.info("Loaded sidecar metadata from %s", sidecar.name)
            return data
    except ImportError:
        logger.debug("PyYAML not available — skipping sidecar metadata")
    except Exception as exc:
        logger.warning("Failed to parse sidecar metadata %s: %s", sidecar.name, exc)

    return {}


def merge_sidecar_metadata(meta: MetadataResult, file_path: Path) -> MetadataResult:
    """Load sidecar metadata and merge it into *meta*.

    Sidecar values only overwrite empty/default fields — they never
    replace metadata that was already extracted from the document itself.
    """
    sidecar = load_sidecar_metadata(file_path)
    if not sidecar:
        return meta

    # Overwrite only if current value is empty/default
    if sidecar.get("title") and not meta.title:
        meta.title = str(sidecar["title"])

    author = sidecar.get("author")
    authors = sidecar.get("authors")
    if not meta.authors:
        if isinstance(authors, list):
            meta.authors = [str(a) for a in authors]
        elif author:
            meta.authors = [str(author)]

    if sidecar.get("date") and not meta.date:
        meta.date = str(sidecar["date"])
    if sidecar.get("language") and not meta.language:
        meta.language = str(sidecar["language"])
    if sidecar.get("publisher") and not meta.publisher:
        meta.publisher = str(sidecar["publisher"])
    if sidecar.get("document_type") and not meta.document_type:
        meta.document_type = str(sidecar["document_type"])
    if sidecar.get("doi") and not meta.doi:
        meta.doi = str(sidecar["doi"])
    if sidecar.get("isbn") and not meta.isbn:
        meta.isbn = str(sidecar["isbn"])
    if sidecar.get("abstract") and not meta.abstract:
        meta.abstract = str(sidecar["abstract"])

    # Keywords: merge lists
    if sidecar.get("keywords") and not meta.keywords:
        kw = sidecar["keywords"]
        if isinstance(kw, list):
            meta.keywords = [str(k) for k in kw]
        elif isinstance(kw, str):
            meta.keywords = [k.strip() for k in kw.split(",")]

    # Rights
    if sidecar.get("license") and not meta.rights.license:
        meta.rights.license = str(sidecar["license"])
    if sidecar.get("license_url") and not meta.rights.license_url:
        meta.rights.license_url = str(sidecar["license_url"])
    if sidecar.get("copyright") and not meta.rights.copyright_holder:
        meta.rights.copyright_holder = str(sidecar["copyright"])
    if sidecar.get("open_access") and not meta.rights.open_access:
        meta.rights.open_access = bool(sidecar["open_access"])

    # Extra fields
    extra = sidecar.get("extra")
    if isinstance(extra, dict) and not meta.source_info.extra:
        meta.source_info.extra = {str(k): str(v) for k, v in extra.items()}

    meta.extraction_method = f"sidecar+{meta.extraction_method}"
    return meta
