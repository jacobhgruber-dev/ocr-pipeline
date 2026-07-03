"""Tests for sidecar metadata (.meta.yaml) loading and merging."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.models import MetadataResult, RightsInfo
from ocr_pipeline.sidecar import load_sidecar_metadata, merge_sidecar_metadata


# ---------------------------------------------------------------------------
# load_sidecar_metadata
# ---------------------------------------------------------------------------


class TestLoadSidecarMetadata:
    """Tests for load_sidecar_metadata function."""

    def test_loads_yaml_sidecar(self, tmp_path: Path) -> None:
        """Load metadata from a .meta.yaml file next to a document."""
        doc = tmp_path / "report.pdf"
        doc.write_text("dummy pdf content")
        sidecar = tmp_path / "report.pdf.meta.yaml"
        sidecar.write_text(
            "title: My Document\nauthor: Jane Researcher\ndate: '2025-06-01'\nlanguage: en\n",
            encoding="utf-8",
        )

        meta = load_sidecar_metadata(doc)
        assert meta == {
            "title": "My Document",
            "author": "Jane Researcher",
            "date": "2025-06-01",
            "language": "en",
        }

    def test_loads_yml_extension(self, tmp_path: Path) -> None:
        """Also looks for .meta.yml as a fallback."""
        doc = tmp_path / "notes.txt"
        doc.write_text("some notes")
        sidecar = tmp_path / "notes.txt.meta.yml"
        sidecar.write_text(
            "title: Fallback Document\ndocument_type: notes\n",
            encoding="utf-8",
        )

        meta = load_sidecar_metadata(doc)
        assert meta["title"] == "Fallback Document"
        assert meta["document_type"] == "notes"

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """No sidecar file → empty dict."""
        doc = tmp_path / "orphan.pdf"
        doc.write_text("no sidecar here")
        meta = load_sidecar_metadata(doc)
        assert meta == {}

    def test_non_dict_yaml_returns_empty(self, tmp_path: Path) -> None:
        """YAML that parses to a non-dict returns empty dict."""
        doc = tmp_path / "list.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "list.pdf.meta.yaml"
        sidecar.write_text("- item1\n- item2\n", encoding="utf-8")

        meta = load_sidecar_metadata(doc)
        assert meta == {}

    def test_malformed_yaml_returns_empty(self, tmp_path: Path) -> None:
        """Malformed YAML returns empty dict (graceful degradation)."""
        doc = tmp_path / "broken.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "broken.pdf.meta.yaml"
        sidecar.write_text(": invalid yaml :::\n\tbroken", encoding="utf-8")

        meta = load_sidecar_metadata(doc)
        assert meta == {}

    def test_with_extra_fields(self, tmp_path: Path) -> None:
        """Extra fields in sidecar are preserved."""
        doc = tmp_path / "paper.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "paper.pdf.meta.yaml"
        sidecar.write_text(
            "title: Research Paper\n"
            "doi: 10.1234/example\n"
            "extra:\n"
            "  collection: Private\n"
            "  notes: Scanned copy\n",
            encoding="utf-8",
        )

        meta = load_sidecar_metadata(doc)
        assert meta["title"] == "Research Paper"
        assert meta["doi"] == "10.1234/example"
        assert isinstance(meta["extra"], dict)
        assert meta["extra"]["collection"] == "Private"


# ---------------------------------------------------------------------------
# merge_sidecar_metadata
# ---------------------------------------------------------------------------


class TestMergeSidecarMetadata:
    """Tests for merge_sidecar_metadata function."""

    def _make_meta(self, **kwargs: str | list[str]) -> MetadataResult:
        """Helper to create a MetadataResult with default empty fields."""
        return MetadataResult(
            title=str(kwargs.get("title", "")),
            authors=kwargs.get("authors", [])
            if isinstance(kwargs.get("authors"), list)
            else [str(kwargs.get("authors", ""))]
            if kwargs.get("authors")
            else [],
            date=str(kwargs.get("date", "")),
            language=str(kwargs.get("language", "")),
            publisher=str(kwargs.get("publisher", "")),
            doi=str(kwargs.get("doi", "")),
            isbn=str(kwargs.get("isbn", "")),
            abstract=str(kwargs.get("abstract", "")),
            document_type=str(kwargs.get("document_type", "")),
            rights=RightsInfo(),
        )

    def test_merges_into_empty_metadata(self, tmp_path: Path) -> None:
        """Sidecar values fill empty fields in MetadataResult."""
        doc = tmp_path / "report.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "report.pdf.meta.yaml"
        sidecar.write_text(
            "title: Injected Title\nauthor: Sidecar Author\ndate: '2024-12-25'\nlanguage: fr\n",
            encoding="utf-8",
        )

        meta = self._make_meta()
        result = merge_sidecar_metadata(meta, doc)

        assert result.title == "Injected Title"
        assert result.authors == ["Sidecar Author"]
        assert result.date == "2024-12-25"
        assert result.language == "fr"

    def test_preserves_existing_fields(self, tmp_path: Path) -> None:
        """Sidecar does NOT overwrite fields that already have values."""
        doc = tmp_path / "paper.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "paper.pdf.meta.yaml"
        sidecar.write_text(
            "title: Should Not Override\ndate: '2000-01-01'\n",
            encoding="utf-8",
        )

        meta = self._make_meta(title="Original Title", date="2025-06-15")
        result = merge_sidecar_metadata(meta, doc)

        # Existing values are preserved
        assert result.title == "Original Title"
        assert result.date == "2025-06-15"

    def test_merges_keywords(self, tmp_path: Path) -> None:
        """Keywords from sidecar are used when meta.keywords is empty."""
        doc = tmp_path / "article.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "article.pdf.meta.yaml"
        sidecar.write_text(
            "keywords:\n  - machine learning\n  - NLP\n  - OCR\n",
            encoding="utf-8",
        )

        meta = self._make_meta()
        result = merge_sidecar_metadata(meta, doc)

        assert "machine learning" in result.keywords
        assert "NLP" in result.keywords
        assert "OCR" in result.keywords

    def test_extraction_method_prefixed(self, tmp_path: Path) -> None:
        """merge_sidecar_metadata prefixes extraction_method with 'sidecar+'."""
        doc = tmp_path / "doc.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "doc.pdf.meta.yaml"
        sidecar.write_text("title: Test\n", encoding="utf-8")

        meta = self._make_meta()
        meta.extraction_method = "pdf-parsing"
        result = merge_sidecar_metadata(meta, doc)

        assert result.extraction_method == "sidecar+pdf-parsing"

    def test_no_sidecar_returns_unchanged(self, tmp_path: Path) -> None:
        """No sidecar file → MetadataResult is returned unchanged."""
        doc = tmp_path / "nometa.pdf"
        doc.write_text("dummy")
        # No .meta.yaml file created

        meta = self._make_meta(title="Standalone")
        result = merge_sidecar_metadata(meta, doc)

        assert result.title == "Standalone"
        assert result.extraction_method == ""  # unchanged

    def test_publisher_and_doi(self, tmp_path: Path) -> None:
        """Publisher and DOI are merged from sidecar when empty."""
        doc = tmp_path / "article.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "article.pdf.meta.yaml"
        sidecar.write_text(
            "publisher: ACM Press\ndoi: 10.1145/1234567\n",
            encoding="utf-8",
        )

        meta = self._make_meta()
        result = merge_sidecar_metadata(meta, doc)

        assert result.publisher == "ACM Press"
        assert result.doi == "10.1145/1234567"

    def test_abstract_merged(self, tmp_path: Path) -> None:
        """Abstract is merged from sidecar when empty."""
        doc = tmp_path / "paper.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "paper.pdf.meta.yaml"
        sidecar.write_text(
            "abstract: This is a comprehensive study of the effects of X on Y.\n",
            encoding="utf-8",
        )

        meta = self._make_meta()
        result = merge_sidecar_metadata(meta, doc)

        assert "comprehensive study" in result.abstract
        assert "effects of X on Y" in result.abstract

    def test_isbn_and_document_type(self, tmp_path: Path) -> None:
        """ISBN and document_type are merged from sidecar when empty."""
        doc = tmp_path / "book.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "book.pdf.meta.yaml"
        sidecar.write_text(
            "isbn: 978-3-16-148410-0\ndocument_type: book\n",
            encoding="utf-8",
        )

        meta = self._make_meta()
        result = merge_sidecar_metadata(meta, doc)

        assert result.isbn == "978-3-16-148410-0"
        assert result.document_type == "book"

    def test_multiple_authors_list(self, tmp_path: Path) -> None:
        """Authors list from sidecar is used when meta.authors is empty."""
        doc = tmp_path / "paper.pdf"
        doc.write_text("dummy")
        sidecar = tmp_path / "paper.pdf.meta.yaml"
        sidecar.write_text(
            "authors:\n  - Alice\n  - Bob\n  - Charlie\n",
            encoding="utf-8",
        )

        meta = self._make_meta()
        result = merge_sidecar_metadata(meta, doc)

        assert result.authors == ["Alice", "Bob", "Charlie"]
