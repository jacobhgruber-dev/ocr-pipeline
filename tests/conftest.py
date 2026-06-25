"""Shared fixtures for OCR pipeline tests."""

from __future__ import annotations

import pytest
from pathlib import Path

from ocr_pipeline.config import PipelineConfig
from ocr_pipeline.models import (
    Block,
    EngineOutput,
    FileIdentity,
    PageResult,
)


@pytest.fixture
def sample_config() -> PipelineConfig:
    """A minimal PipelineConfig with required fields."""
    return PipelineConfig(input_dir=Path("/tmp/test"), output_dir=Path("/tmp/out"))


@pytest.fixture
def sample_page() -> PageResult:
    return PageResult(sha256="abc123", page_index=0, page_label="page_0001")


@pytest.fixture
def sample_engine_output() -> EngineOutput:
    return EngineOutput(engine="marker", text="Sample OCR text", duration_sec=2.5)


@pytest.fixture
def sample_file_identity() -> FileIdentity:
    return FileIdentity(
        relative_path="test/doc.pdf",
        size_bytes=12345,
        mtime_epoch=1700000000.0,
        sha256="deadbeefcafe",
    )


@pytest.fixture
def sample_block() -> Block:
    return Block(
        type="heading",
        text="Chapter 1",
        bbox=(10.0, 20.0, 200.0, 40.0),
        confidence=0.95,
        children=[
            Block(type="text", text="Introduction paragraph.", confidence=0.88),
        ],
    )
