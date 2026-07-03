"""DOI and ISBN identifier resolution for metadata enrichment.

Resolves DOIs via the CrossRef API and ISBNs via the OpenLibrary API
using only stdlib (urllib).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .models import MetadataResult

USER_AGENT = "ocr-pipeline/0.2.0 (mailto:your-email@example.com)"
CROSSREF_BASE = "https://api.crossref.org/works/"
OPENLIBRARY_BASE = "https://openlibrary.org/isbn/"


def _fetch_json(url: str, timeout: float) -> dict[str, Any]:
    """Fetch a URL and parse the response as JSON.

    Returns an empty dict on any failure (network, HTTP, malformed JSON).
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _crossref_fetch(doi: str, timeout: float) -> dict[str, Any]:
    """Fetch CrossRef data with a single 429 retry."""
    url = CROSSREF_BASE + doi
    result = _fetch_json(url, timeout)
    # Rate-limit retry: CrossRef returns 429 that turns into an empty dict
    # from _fetch_json. We retry once after sleeping.
    if not result:
        time.sleep(2)
        result = _fetch_json(url, timeout)
    return result


def resolve_doi(doi: str, timeout: float = 10.0) -> dict[str, str]:
    """Resolve a DOI via CrossRef API.

    Returns dict with keys: title, author, journal, volume, issue, year,
    publisher, doi, abstract, type, language, license_url.
    Returns empty dict on failure (invalid DOI, network error, etc.).
    """
    if not doi or not isinstance(doi, str):
        return {}

    cleaned = doi.strip()
    if not cleaned:
        return {}

    # Strip DOI URL prefix if present
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
    ):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break

    data = _crossref_fetch(cleaned, timeout)
    if not data:
        return {}

    try:
        msg = data.get("message", {})
    except (AttributeError, TypeError):
        return {}

    if not isinstance(msg, dict) or not msg:
        return {}

    result: dict[str, str] = {}
    result["doi"] = cleaned

    # Title
    title_list: list[str] = msg.get("title", [])
    if title_list:
        result["title"] = str(title_list[0])

    # Author(s): concatenate given + family names
    authors: list[dict[str, str]] = msg.get("author", [])
    if authors:
        names: list[str] = []
        for a in authors:
            given = a.get("given", "")
            family = a.get("family", "")
            if given and family:
                names.append(f"{given} {family}")
            elif family:
                names.append(family)
            elif given:
                names.append(given)
        if names:
            result["author"] = "; ".join(names)

    # Journal / container
    container: list[str] = msg.get("container-title", [])
    if container:
        result["journal"] = str(container[0])

    result["volume"] = str(msg.get("volume", ""))
    result["issue"] = str(msg.get("issue", ""))

    # Publication year
    issued = msg.get("issued", {})
    if isinstance(issued, dict):
        date_parts = issued.get("date-parts", [])
        if date_parts and date_parts[0]:
            result["year"] = str(date_parts[0][0])

    result["publisher"] = str(msg.get("publisher", ""))

    # Abstract
    abstract = msg.get("abstract", "")
    if isinstance(abstract, str):
        result["abstract"] = abstract

    # Type
    result["type"] = str(msg.get("type", ""))

    # Language
    result["language"] = str(msg.get("language", ""))

    # License URL
    license_list: list[dict[str, Any]] = msg.get("license", [])
    if license_list:
        for lic in license_list:
            url = lic.get("URL", "")
            if url:
                result["license_url"] = str(url)
                break

    return result


def resolve_isbn(isbn: str, timeout: float = 10.0) -> dict[str, str]:
    """Resolve an ISBN via OpenLibrary API.

    Returns dict with keys: title, author, publisher, year, isbn, language,
    subjects.
    Returns empty dict on failure (invalid ISBN, network error, etc.).
    """
    if not isbn or not isinstance(isbn, str):
        return {}

    # Clean ISBN: strip hyphens and whitespace
    cleaned = isbn.strip().replace("-", "").replace(" ", "")
    if not cleaned:
        return {}

    url = OPENLIBRARY_BASE + cleaned + ".json"
    data = _fetch_json(url, timeout)
    if not data:
        return {}

    result: dict[str, str] = {}
    result["isbn"] = cleaned

    # Title
    title = data.get("title")
    if isinstance(title, str):
        result["title"] = title

    # Authors: OpenLibrary returns list of author keys; we'd need to resolve
    # each one. For now, return author names from works if available, or
    # indicate author count. In practice, OpenLibrary ISBN endpoint may
    # include "authors" as a list of dicts with "name".
    authors_raw = data.get("authors", [])
    if authors_raw and isinstance(authors_raw, list):
        names: list[str] = []
        for a in authors_raw:
            if isinstance(a, dict):
                name = a.get("name", "")
                if name:
                    names.append(str(name))
        if names:
            result["author"] = "; ".join(names)

    # Publisher
    publishers_raw = data.get("publishers", [])
    if publishers_raw and isinstance(publishers_raw, list):
        result["publisher"] = str(publishers_raw[0])
    elif isinstance(data.get("publisher"), str):
        result["publisher"] = str(data["publisher"])

    # Year: OpenLibrary returns publish_date as a string like "2020" or "Mar 2020"
    publish_date = data.get("publish_date", "")
    if isinstance(publish_date, str) and publish_date:
        # Try to extract a 4-digit year
        import re

        match = re.search(r"\b(\d{4})\b", publish_date)
        if match:
            result["year"] = match.group(1)

    # Language
    languages = data.get("languages", [])
    if languages and isinstance(languages, list):
        for lang in languages:
            if isinstance(lang, dict):
                key = lang.get("key", "")
                if key:
                    # key is like "/languages/eng"
                    code = key.rsplit("/", 1)[-1]
                    result["language"] = code
                    break

    # Subjects
    subjects_raw = data.get("subjects", [])
    if subjects_raw and isinstance(subjects_raw, list):
        result["subjects"] = "; ".join(str(s) for s in subjects_raw)

    return result


def enrich_metadata(meta: MetadataResult, timeout: float = 10.0) -> MetadataResult:
    """Enrich metadata by resolving any DOIs/ISBNs found in the metadata.

    Only fills empty fields — never overwrites existing data.
    Resolves DOIs first (more comprehensive), then ISBNs.
    Returns the same MetadataResult object (mutated in place).
    """
    # Resolve DOI first
    if meta.doi:
        info = resolve_doi(meta.doi, timeout=timeout)
        if info:
            if not meta.title:
                meta.title = info.get("title", "")
            if not meta.authors:
                author = info.get("author", "")
                if author:
                    meta.authors = [author]
            if not meta.publisher:
                meta.publisher = info.get("publisher", "")
            if not meta.year:
                meta.year = info.get("year", "")
            if not meta.journal:
                meta.journal = info.get("journal", "")
            if not meta.volume:
                meta.volume = info.get("volume", "")
            if not meta.issue:
                meta.issue = info.get("issue", "")
            if not meta.abstract:
                meta.abstract = info.get("abstract", "")
            if not meta.language:
                meta.language = info.get("language", "")
            if "type" in info and meta.document_type:
                pass  # Don't overwrite document_type; keep separate
            elif "type" in info and not meta.document_type:
                meta.document_type = info.get("type", "")  # type: ignore[union-attr]

    # Then resolve ISBN
    if meta.isbn:
        info = resolve_isbn(meta.isbn, timeout=timeout)
        if info:
            if not meta.title:
                meta.title = info.get("title", "")
            if not meta.authors:
                author = info.get("author", "")
                if author:
                    meta.authors = [author]
            if not meta.publisher:
                meta.publisher = info.get("publisher", "")
            if not meta.year:
                meta.year = info.get("year", "")
            if not meta.language:
                meta.language = info.get("language", "")
            # Add subjects as keywords if not already set
            subjects = info.get("subjects", "")
            if subjects and not meta.keywords:
                meta.keywords = [s.strip() for s in subjects.split(";") if s.strip()]

    return meta
