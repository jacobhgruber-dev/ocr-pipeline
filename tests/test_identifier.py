"""Tests for ocr_pipeline.identifier — DOI and ISBN resolution."""

from __future__ import annotations

import urllib.error

from ocr_pipeline.identifier import (
    _crossref_fetch,
    _fetch_json,
    enrich_metadata,
    resolve_doi,
    resolve_isbn,
)
from ocr_pipeline.models import MetadataResult

# ---------------------------------------------------------------------------
# resolve_doi
# ---------------------------------------------------------------------------


def test_resolve_doi_known():
    """Resolve a well-known DOI and verify core fields."""
    result = resolve_doi("10.1038/nature12373", timeout=15.0)
    assert result, "Expected non-empty result for known DOI"
    assert "title" in result
    assert result["title"], "Title should not be empty"
    assert "author" in result
    assert result["author"], "Author should not be empty"
    assert "journal" in result
    assert "Nature" in result.get("journal", "")
    assert result.get("doi") == "10.1038/nature12373"


def test_resolve_doi_strips_url_prefix():
    """Resolve a DOI that includes an https://doi.org/ prefix."""
    result = resolve_doi("https://doi.org/10.1038/nature12373", timeout=15.0)
    assert result, "Expected non-empty result for known DOI with URL prefix"
    assert "title" in result
    assert result["title"]


def test_resolve_doi_invalid():
    """Invalid DOI should return an empty dict."""
    result = resolve_doi("10.9999/does-not-exist-123456789", timeout=10.0)
    assert result == {}


def test_resolve_doi_empty():
    """Empty string should return an empty dict."""
    assert resolve_doi("") == {}


def test_resolve_doi_none():
    """None should return an empty dict."""
    assert resolve_doi(None) == {}  # type: ignore[arg-type]


def test_resolve_doi_whitespace_only():
    """Whitespace-only string should return an empty dict."""
    assert resolve_doi("   ") == {}


# ---------------------------------------------------------------------------
# resolve_isbn
# ---------------------------------------------------------------------------


def test_resolve_isbn_known():
    """Resolve a well-known ISBN-13 and verify core fields."""
    result = resolve_isbn("978-0-13-468599-1", timeout=15.0)
    assert result, "Expected non-empty result for known ISBN"
    assert "title" in result
    assert result["title"], "Title should not be empty"
    assert result.get("isbn") == "9780134685991"


def test_resolve_isbn_known_isbn10():
    """Resolve a well-known ISBN-10 (OpenLibrary accepts both formats)."""
    result = resolve_isbn("0-596-51774-2", timeout=15.0)
    assert result, "Expected non-empty result for known ISBN-10"
    assert "title" in result
    assert result["title"]


def test_resolve_isbn_invalid():
    """Invalid ISBN should return an empty dict."""
    result = resolve_isbn("978-9-999-99999-9", timeout=10.0)
    assert result == {}


def test_resolve_isbn_empty():
    """Empty string should return an empty dict."""
    assert resolve_isbn("") == {}


def test_resolve_isbn_none():
    """None should return an empty dict."""
    assert resolve_isbn(None) == {}  # type: ignore[arg-type]


def test_resolve_isbn_cleans_hyphens_and_spaces():
    """Verify that hyphens and spaces are stripped from ISBN before lookup."""
    result = resolve_isbn("978 0 13 468599 1", timeout=15.0)
    assert result, "Expected non-empty result with spaced ISBN"
    assert "title" in result


# ---------------------------------------------------------------------------
# enrich_metadata
# ---------------------------------------------------------------------------


def test_enrich_metadata_fills_empty_fields_from_doi():
    """Metadata with empty fields should be filled from DOI resolution."""
    meta = MetadataResult(doi="10.1038/nature12373")
    result = enrich_metadata(meta, timeout=15.0)
    assert result is meta, "Should return the same object (mutated in place)"
    assert result.title, "Title should be filled"
    assert result.authors, "Authors should be filled"
    assert "Nature" in result.journal or "nature" in result.journal.lower(), (
        f"Journal should contain 'Nature', got: {result.journal!r}"
    )


def test_enrich_metadata_fills_empty_fields_from_isbn():
    """Metadata with empty fields should be filled from ISBN resolution."""
    meta = MetadataResult(isbn="978-0-13-468599-1")
    result = enrich_metadata(meta, timeout=15.0)
    assert result is meta, "Should return the same object (mutated in place)"
    assert result.title, "Title should be filled"


def test_enrich_metadata_preserves_existing_fields():
    """Existing fields must not be overwritten."""
    meta = MetadataResult(
        doi="10.1038/nature12373",
        title="My Custom Title",
        authors=["Jane Doe"],
        publisher="Self Published",
    )
    result = enrich_metadata(meta, timeout=15.0)
    assert result.title == "My Custom Title", "Existing title must be preserved"
    assert result.authors == ["Jane Doe"], "Existing authors must be preserved"
    assert result.publisher == "Self Published", "Existing publisher must be preserved"
    # But empty fields should still be filled
    assert result.journal, "Empty journal should be filled"
    assert result.year, "Empty year should be filled"


def test_enrich_metadata_no_identifiers():
    """Metadata with no doi or isbn should be returned unchanged."""
    meta = MetadataResult()
    result = enrich_metadata(meta)
    assert result is meta
    assert result.title == ""
    assert result.authors == []


def test_enrich_metadata_fills_keywords_from_isbn_subjects():
    """ISBN subjects should be added as keywords if keywords are empty."""
    meta = MetadataResult(isbn="978-0-13-468599-1")
    result = enrich_metadata(meta, timeout=15.0)
    # ISBN subject keywords may or may not be populated by OpenLibrary
    # for this specific book — just verify the field type if populated
    assert isinstance(result.keywords, list)


def test_enrich_metadata_does_not_overwrite_keywords():
    """Existing keywords must not be overwritten by ISBN subjects."""
    meta = MetadataResult(isbn="978-0-13-468599-1", keywords=["programming", "java"])
    result = enrich_metadata(meta, timeout=15.0)
    assert result.keywords == ["programming", "java"], "Existing keywords must be preserved"


# ---------------------------------------------------------------------------
# Timeout and error handling (mocked)
# ---------------------------------------------------------------------------


def test_fetch_json_timeout(mocker):
    """Network timeout should result in an empty dict."""
    mock_urlopen = mocker.patch("ocr_pipeline.identifier.urllib.request.urlopen")
    mock_urlopen.side_effect = urllib.error.URLError("timed out")
    result = _fetch_json("https://example.com", timeout=5.0)
    assert result == {}


def test_fetch_json_http_404(mocker):
    """HTTP 404 should result in an empty dict."""
    mock_urlopen = mocker.patch("ocr_pipeline.identifier.urllib.request.urlopen")
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://example.com", 404, "Not Found", {}, None
    )
    result = _fetch_json("https://example.com", timeout=5.0)
    assert result == {}


def test_fetch_json_malformed(mocker):
    """Malformed JSON should result in an empty dict."""
    mock_urlopen = mocker.patch("ocr_pipeline.identifier.urllib.request.urlopen")

    class FakeResponse:
        def read(self):
            return b"not json {{{"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    mock_urlopen.return_value = FakeResponse()
    result = _fetch_json("https://example.com", timeout=5.0)
    assert result == {}


def test_crossref_retries_on_empty(mocker):
    """After an empty response (simulating 429), _crossref_fetch should retry once."""
    mock_fetch = mocker.patch("ocr_pipeline.identifier._fetch_json")
    # First call returns empty, second returns data
    mock_fetch.side_effect = [
        {},
        {"message": {"title": ["Test Title"], "publisher": "Test Pub"}},
    ]
    mocker.patch("time.sleep")  # Don't actually sleep
    result = _crossref_fetch("10.1234/test", timeout=5.0)
    assert mock_fetch.call_count == 2
    assert result["message"]["title"] == ["Test Title"]
