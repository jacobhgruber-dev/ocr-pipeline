"""Tests for VLM merge protocol and stub merger."""

from __future__ import annotations

from pathlib import Path

from ocr_pipeline.merger import (
    DefaultVlmMerger,
    StubVlmMerger,
    VlmMerger,
)


class TestStubVlmMerger:
    def test_returns_canned_text(self):
        stub = StubVlmMerger(canned_text="CUSTOM STUB OUTPUT")
        result, raw_json, model_used, cost = stub.merge(
            image_path=Path("/fake/image.png"),
            engine_outputs=[],
            page_index=0,
            pdf_identifier="test.pdf",
            system_prompt="",
            model="test-model",
            fallback_model="fallback",
            max_tokens=100,
            timeout_sec=30.0,
        )
        assert result == "CUSTOM STUB OUTPUT"
        assert model_used == "test-model"
        assert cost == 0.0

    def test_returns_canned_text_with_model_fallback(self):
        """When model is empty string, stub uses 'stub' as model name."""
        stub = StubVlmMerger()
        result, raw_json, model_used, cost = stub.merge(
            image_path=Path("/a.png"),
            engine_outputs=[],
            page_index=0,
            pdf_identifier="x",
            system_prompt="",
            model="",
            fallback_model="fb",
            max_tokens=100,
            timeout_sec=30.0,
        )
        assert result == "STUB MERGED TEXT"
        assert model_used == "stub"
        assert cost == 0.0

    def test_raw_json_is_stub_json(self):
        stub = StubVlmMerger()
        result, raw_json, model_used, cost = stub.merge(
            image_path=Path("/a.png"),
            engine_outputs=[],
            page_index=0,
            pdf_identifier="x",
            system_prompt="",
            model="m",
            fallback_model="fb",
            max_tokens=100,
            timeout_sec=30.0,
        )
        assert '"stub": true' in raw_json

    def test_call_count_increments(self):
        stub = StubVlmMerger()
        assert stub.call_count == 0
        for _ in range(3):
            stub.merge(
                image_path=Path("/a.png"),
                engine_outputs=[],
                page_index=0,
                pdf_identifier="x",
                system_prompt="",
                model="m",
                fallback_model="fb",
                max_tokens=100,
                timeout_sec=30.0,
            )
        assert stub.call_count == 3

    def test_zero_cost(self):
        stub = StubVlmMerger()
        result, raw_json, model_used, cost = stub.merge(
            image_path=Path("/a.png"),
            engine_outputs=[],
            page_index=0,
            pdf_identifier="x",
            system_prompt="",
            model="m",
            fallback_model="fb",
            max_tokens=100,
            timeout_sec=30.0,
        )
        assert cost == 0.0


class TestVlmMergerProtocol:
    def test_stub_satisfies_protocol(self):
        stub = StubVlmMerger()
        assert isinstance(stub, VlmMerger)

    def test_default_is_instance_of_protocol(self):
        merger = DefaultVlmMerger()
        assert isinstance(merger, VlmMerger)


class TestDefaultVlmMerger:
    def test_can_be_instantiated(self):
        """Sanity check — does not make real API calls."""
        merger = DefaultVlmMerger()
        assert merger is not None
