"""Tests for language passthrough to OCR engines and pipeline."""

from __future__ import annotations

import inspect
from pathlib import Path

from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.engines import (
    GoogleDocAiEngine,
    GrobidEngine,
    MarkerEngine,
    MathpixEngine,
    OcrEngine,
    Surya2Engine,
)
from ocr_pipeline.mcp_server import ocr_page


# ---------------------------------------------------------------------------
# OcrEngine protocol signature
# ---------------------------------------------------------------------------


class TestOcrEngineProtocol:
    def test_recognize_has_languages_parameter(self):
        sig = inspect.signature(OcrEngine.recognize)
        assert "languages" in sig.parameters

    def test_languages_has_none_default(self):
        sig = inspect.signature(OcrEngine.recognize)
        param = sig.parameters["languages"]
        assert param.default is None

    def test_languages_type_is_optional_list_of_str(self):
        sig = inspect.signature(OcrEngine.recognize)
        param = sig.parameters["languages"]
        # Protocol param annotation: list[str] | None
        ann_str = str(param.annotation)
        assert "None" in ann_str
        assert "list" in ann_str.lower()


# ---------------------------------------------------------------------------
# MarkerEngine
# ---------------------------------------------------------------------------


class TestMarkerEngineLanguages:
    def test_recognize_signature_has_languages(self):
        sig = inspect.signature(MarkerEngine.recognize)
        assert "languages" in sig.parameters

    def test_languages_defaults_to_none(self):
        sig = inspect.signature(MarkerEngine.recognize)
        assert sig.parameters["languages"].default is None

    def test_languages_positioned_after_timeout(self):
        sig = inspect.signature(MarkerEngine.recognize)
        param_names = list(sig.parameters.keys())
        # self, image_path, page_index, timeout_sec, languages
        lang_idx = param_names.index("languages")
        timeout_idx = param_names.index("timeout_sec")
        assert lang_idx > timeout_idx


# ---------------------------------------------------------------------------
# MathpixEngine
# ---------------------------------------------------------------------------


class TestMathpixEngineLanguages:
    def test_recognize_signature_has_languages(self):
        sig = inspect.signature(MathpixEngine.recognize)
        assert "languages" in sig.parameters

    def test_languages_defaults_to_none(self):
        sig = inspect.signature(MathpixEngine.recognize)
        assert sig.parameters["languages"].default is None

    def test_instantiate_without_args(self):
        """MathpixEngine can be constructed without args (uses CredentialStore)."""
        engine = MathpixEngine()
        assert engine.engine_name == "mathpix"


# ---------------------------------------------------------------------------
# Surya2Engine
# ---------------------------------------------------------------------------


class TestSurya2EngineLanguages:
    def test_recognize_signature_has_languages(self):
        sig = inspect.signature(Surya2Engine.recognize)
        assert "languages" in sig.parameters

    def test_languages_before_pdf_path(self):
        sig = inspect.signature(Surya2Engine.recognize)
        param_names = list(sig.parameters.keys())
        lang_idx = param_names.index("languages")
        pdf_idx = param_names.index("pdf_path")
        assert lang_idx < pdf_idx, (
            f"languages (pos {lang_idx}) should be before pdf_path (pos {pdf_idx})"
        )

    def test_languages_defaults_to_none(self):
        sig = inspect.signature(Surya2Engine.recognize)
        assert sig.parameters["languages"].default is None


# ---------------------------------------------------------------------------
# GrobidEngine
# ---------------------------------------------------------------------------


class TestGrobidEngineLanguages:
    def test_recognize_signature_has_languages(self):
        sig = inspect.signature(GrobidEngine.recognize)
        assert "languages" in sig.parameters

    def test_languages_defaults_to_none(self):
        sig = inspect.signature(GrobidEngine.recognize)
        assert sig.parameters["languages"].default is None


# ---------------------------------------------------------------------------
# GoogleDocAiEngine
# ---------------------------------------------------------------------------


class TestGoogleDocAiEngineLanguages:
    def test_recognize_signature_has_languages(self):
        sig = inspect.signature(GoogleDocAiEngine.recognize)
        assert "languages" in sig.parameters

    def test_languages_defaults_to_none(self):
        sig = inspect.signature(GoogleDocAiEngine.recognize)
        assert sig.parameters["languages"].default is None


# ---------------------------------------------------------------------------
# PipelineConfig
# ---------------------------------------------------------------------------


class TestPipelineConfigLanguages:
    def test_default_languages_is_en(self):
        cfg = PipelineConfig(input_dir=Path("/tmp/in"), output_dir=Path("/tmp/out"))
        assert cfg.languages == ["en"]

    def test_custom_languages_persisted(self):
        cfg = PipelineConfig(
            input_dir=Path("/tmp/in"),
            output_dir=Path("/tmp/out"),
            languages=["en", "fr", "de"],
        )
        assert cfg.languages == ["en", "fr", "de"]

    def test_empty_languages_list_allowed(self):
        cfg = PipelineConfig(
            input_dir=Path("/tmp/in"),
            output_dir=Path("/tmp/out"),
            languages=[],
        )
        assert cfg.languages == []

    def test_single_language(self):
        cfg = PipelineConfig(
            input_dir=Path("/tmp/in"),
            output_dir=Path("/tmp/out"),
            languages=["la"],
        )
        assert cfg.languages == ["la"]

    def test_multiple_languages_with_ancient(self):
        cfg = PipelineConfig(
            input_dir=Path("/tmp/in"),
            output_dir=Path("/tmp/out"),
            languages=["en", "la", "grc", "he"],
        )
        assert cfg.languages == ["en", "la", "grc", "he"]


# ---------------------------------------------------------------------------
# MCP server ocr_page
# ---------------------------------------------------------------------------


class TestMcpServerOcrPage:
    def test_ocr_page_signature_has_languages(self):
        sig = inspect.signature(ocr_page)
        assert "languages" in sig.parameters

    def test_languages_defaults_to_en(self):
        sig = inspect.signature(ocr_page)
        assert sig.parameters["languages"].default == "en"

    def test_languages_is_a_string_parameter(self):
        sig = inspect.signature(ocr_page)
        ann = sig.parameters["languages"].annotation
        # from __future__ import annotations makes this a string "str"
        assert ann is str or str(ann) in ("str", "<class 'str'>")
