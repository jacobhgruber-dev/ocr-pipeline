"""Tests for multi-format document sources (DocumentSource implementations)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocr_pipeline.errors import ConfigError
from ocr_pipeline.sources import (
    CsvSource,
    DocxSource,
    EpubSource,
    ExcelSource,
    ImageSource,
    PdfSource,
    PptxSource,
    TxtSource,
    detect_source,
)


# ---------------------------------------------------------------------------
# Factory detection
# ---------------------------------------------------------------------------


class TestDetectSource:
    def test_detect_pdf(self) -> None:
        pdf = Path("tests/fixtures/general/mixed_format.pdf")
        source = detect_source(pdf)
        assert isinstance(source, PdfSource)
        assert source.source_format == "pdf"
        assert source.page_count >= 1

    def test_detect_txt_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        source = detect_source(f)
        assert isinstance(source, TxtSource)
        assert source.source_format == "txt"

    def test_detect_unsupported_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "test.xyz"
        f.write_text("nope")
        with pytest.raises(ConfigError, match="Unsupported"):
            detect_source(f)


# ---------------------------------------------------------------------------
# PdfSource
# ---------------------------------------------------------------------------


class TestPdfSource:
    def test_basic(self) -> None:
        pdf = Path("tests/fixtures/general/mixed_format.pdf")
        source = PdfSource(pdf)
        assert source.source_format == "pdf"
        assert source.source_mimetype == "application/pdf"
        assert source.page_count >= 1

    def test_render_page(self, tmp_path: Path) -> None:
        pdf = Path("tests/fixtures/general/mixed_format.pdf")
        source = PdfSource(pdf)
        png = source.render_page(0, tmp_path, dpi=72)
        assert png.exists()
        assert png.suffix == ".png"
        assert png.stat().st_size > 100

    def test_extract_text(self, tmp_path: Path) -> None:
        pdf = Path("tests/fixtures/general/mixed_format.pdf")
        source = PdfSource(pdf)
        text, saved = source.extract_text(0, tmp_path)
        assert isinstance(text, str)
        assert saved is not None
        assert saved.exists()

    def test_extract_text_empty_page(self, tmp_path: Path) -> None:
        """Out-of-range page raises RenderError."""
        from ocr_pipeline.errors import RenderError

        pdf = Path("tests/fixtures/general/mixed_format.pdf")
        source = PdfSource(pdf)
        with pytest.raises(RenderError, match="out of range"):
            source.extract_text(999, tmp_path)


# ---------------------------------------------------------------------------
# TxtSource
# ---------------------------------------------------------------------------


class TestTxtSource:
    def test_basic_utf8(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_text("Hello world\nLine two\n", encoding="utf-8")
        source = TxtSource(f)
        assert source.source_format == "txt"
        assert source.page_count == 1

    def test_extract_text(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_text("test content", encoding="utf-8")
        source = TxtSource(f)
        out_dir = tmp_path / "out"
        text, saved = source.extract_text(0, out_dir)
        assert "test content" in text
        assert saved is not None
        assert saved.exists()

    def test_cached_read(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_text("cached", encoding="utf-8")
        source = TxtSource(f)
        text1, _ = source.extract_text(0, tmp_path / "out1")
        text2, _ = source.extract_text(0, tmp_path / "out2")
        assert text1 == text2 == "cached"

    def test_render_page_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_text("text", encoding="utf-8")
        source = TxtSource(f)
        with pytest.raises(NotImplementedError, match="not supported"):
            source.render_page(0, tmp_path)


# ---------------------------------------------------------------------------
# ImageSource
# ---------------------------------------------------------------------------


class TestImageSource:
    def test_basic(self) -> None:
        """Use an existing render PNG from fixtures if available."""
        renders = list(Path("tests/fixtures").rglob("page_0001.png"))
        if not renders:
            pytest.skip("No test PNG found in fixtures")
        source = ImageSource(renders[0])
        assert source.source_format == "image"
        assert source.page_count == 1

    def test_extract_text_returns_empty(self) -> None:
        """Images have no extractable text — OCR must handle them."""
        renders = list(Path("tests/fixtures").rglob("page_0001.png"))
        if not renders:
            pytest.skip("No test PNG found in fixtures")
        source = ImageSource(renders[0])
        text, saved = source.extract_text(0, Path("/tmp"))
        assert text == ""
        assert saved is None

    def test_render_page_produces_output(self, tmp_path: Path) -> None:
        """ImageSource.render_page saves a PNG to the output directory."""
        renders = list(Path("tests/fixtures").rglob("page_0001.png"))
        if not renders:
            pytest.skip("No test PNG found in fixtures")
        source = ImageSource(renders[0])
        png = source.render_page(0, tmp_path)
        assert png.exists()
        assert png.suffix == ".png"
        assert png.stat().st_size > 100


# ---------------------------------------------------------------------------
# DocxSource
# ---------------------------------------------------------------------------


class TestDocxSource:
    @pytest.fixture()
    def docx_path(self, tmp_path: Path) -> Path:
        try:
            from docx import Document
        except ImportError:
            pytest.skip("python-docx not installed")

        doc = Document()
        doc.core_properties.title = "Test Title"
        doc.core_properties.author = "Test Author"
        doc.add_heading("Heading 1", level=1)
        doc.add_paragraph("This is a test paragraph.")
        doc.add_paragraph("Second paragraph with more text.")

        path = tmp_path / "test.docx"
        doc.save(str(path))
        return path

    def test_basic(self, docx_path: Path) -> None:
        source = DocxSource(docx_path)
        assert source.source_format == "docx"
        assert source.page_count == 1

    def test_extract_text(self, docx_path: Path, tmp_path: Path) -> None:
        source = DocxSource(docx_path)
        text, saved = source.extract_text(0, tmp_path)
        assert "Heading 1" in text
        assert "test paragraph" in text
        assert saved is not None


# ---------------------------------------------------------------------------
# CsvSource
# ---------------------------------------------------------------------------


class TestCsvSource:
    def test_basic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n", encoding="utf-8")
        source = CsvSource(f)
        assert source.source_format == "csv"
        assert source.page_count == 1

    def test_extract_text(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("col1,col2\na,b\nc,d\n", encoding="utf-8")
        source = CsvSource(f)
        text, saved = source.extract_text(0, tmp_path / "out")
        assert "col1" in text
        assert "col2" in text
        assert "a | b" in text.lower().replace(" ", "") or "a" in text
        assert saved is not None

    def test_extract_text_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.csv"
        f.write_text("col1,col2\n", encoding="utf-8")
        source = CsvSource(f)
        text, _ = source.extract_text(0, tmp_path / "out")
        assert isinstance(text, str)  # doesn't crash


# ---------------------------------------------------------------------------
# EpubSource
# ---------------------------------------------------------------------------


class TestEpubSource:
    @pytest.fixture()
    def epub_path(self, tmp_path: Path) -> Path:
        try:
            from ebooklib import epub
        except ImportError:
            pytest.skip("EbookLib not installed")

        book = epub.EpubBook()
        book.set_identifier("test-123")
        book.set_title("Test Book")
        book.set_language("en")
        book.add_author("Jane Author")

        ch1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml")
        ch1.content = (
            "<html><body><h1>Chapter One</h1><p>This is chapter one text.</p></body></html>"
        )
        book.add_item(ch1)

        ch2 = epub.EpubHtml(title="Chapter 2", file_name="ch2.xhtml")
        ch2.content = "<html><body><h1>Chapter Two</h1><p>Chapter two content.</p></body></html>"
        book.add_item(ch2)

        book.spine = ["nav", ch1, ch2]
        book.toc = [ch1, ch2]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        path = tmp_path / "test.epub"
        epub.write_epub(str(path), book)
        return path

    def test_basic(self, epub_path: Path) -> None:
        source = EpubSource(epub_path)
        assert source.source_format == "epub"
        assert source.page_count >= 1

    def test_extract_text(self, epub_path: Path, tmp_path: Path) -> None:
        source = EpubSource(epub_path)
        text, saved = source.extract_text(0, tmp_path)
        assert isinstance(text, str)
        assert len(text) > 0
        assert saved is not None


# ---------------------------------------------------------------------------
# PptxSource
# ---------------------------------------------------------------------------


class TestPptxSource:
    @pytest.fixture()
    def pptx_path(self, tmp_path: Path) -> Path:
        try:
            from pptx import Presentation
        except ImportError:
            pytest.skip("python-pptx not installed")

        prs = Presentation()
        prs.core_properties.title = "Test Presentation"

        slide1 = prs.slides.add_slide(prs.slide_layouts[0])
        slide1.shapes.title.text = "Slide 1 Title"
        slide1.notes_slide.notes_text_frame.text = "Speaker notes for slide 1"

        slide2 = prs.slides.add_slide(prs.slide_layouts[1])
        slide2.shapes.title.text = "Slide 2 Title"

        path = tmp_path / "test.pptx"
        prs.save(str(path))
        return path

    def test_basic(self, pptx_path: Path) -> None:
        source = PptxSource(pptx_path)
        assert source.source_format == "pptx"
        assert source.page_count == 2  # 2 slides

    def test_extract_text(self, pptx_path: Path, tmp_path: Path) -> None:
        source = PptxSource(pptx_path)
        text, saved = source.extract_text(0, tmp_path)
        assert "Slide 1 Title" in text
        assert "Speaker notes" in text
        assert saved is not None

    def test_extract_text_page2(self, pptx_path: Path, tmp_path: Path) -> None:
        source = PptxSource(pptx_path)
        text, saved = source.extract_text(1, tmp_path / "p2")
        assert "Slide 2 Title" in text
        assert saved is not None


# ---------------------------------------------------------------------------
# ExcelSource
# ---------------------------------------------------------------------------


class TestExcelSource:
    @pytest.fixture()
    def xlsx_path(self, tmp_path: Path) -> Path:
        try:
            from openpyxl import Workbook
        except ImportError:
            pytest.skip("openpyxl not installed")

        wb = Workbook()
        wb.properties.title = "Test Workbook"
        wb.properties.creator = "Test Creator"

        ws = wb.active
        ws.title = "Data"
        ws.append(["Name", "Value", "Date"])
        ws.append(["Alpha", "10", "2024-01-01"])
        ws.append(["Beta", "20", "2024-06-15"])

        ws2 = wb.create_sheet("Summary")
        ws2.append(["Total", "30"])

        path = tmp_path / "test.xlsx"
        wb.save(str(path))
        return path

    def test_basic(self, xlsx_path: Path) -> None:
        source = ExcelSource(xlsx_path)
        assert source.source_format == "excel"
        assert source.page_count == 2  # 2 sheets

    def test_extract_text(self, xlsx_path: Path, tmp_path: Path) -> None:
        source = ExcelSource(xlsx_path)
        text, saved = source.extract_text(0, tmp_path)
        assert "Alpha" in text
        assert "Value" in text
        assert saved is not None

    def test_extract_text_sheet2(self, xlsx_path: Path, tmp_path: Path) -> None:
        source = ExcelSource(xlsx_path)
        text, saved = source.extract_text(1, tmp_path / "s2")
        assert "Total" in text
        assert saved is not None
