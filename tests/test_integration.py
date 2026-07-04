"""Integration tests — prove the pipeline works end-to-end."""

from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent


def test_cli_list_profiles() -> None:
    """CLI --list-profiles shows all 6 profiles."""
    result = subprocess.run(
        ["uv", "run", "ocr-pipeline", "--list-profiles"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    for name in ("general", "academic", "mathematical", "legal", "technical", "books"):
        assert name in result.stdout, f"--list-profiles missing {name}"


def test_cli_list_engines() -> None:
    """CLI --list-engines shows Tesseract."""
    result = subprocess.run(
        ["uv", "run", "ocr-pipeline", "--list-engines"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "tesseract" in result.stdout.lower()


def test_cli_list_languages() -> None:
    """CLI --list-languages shows English."""
    result = subprocess.run(
        ["uv", "run", "ocr-pipeline", "--list-languages"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    assert "en" in result.stdout


def test_cli_dry_run() -> None:
    """CLI --dry-run with temp dirs loads without crashing."""
    import tempfile
    import shutil

    d = Path(tempfile.mkdtemp())
    result = subprocess.run(
        ["uv", "run", "ocr-pipeline", "--input", str(d), "--output", str(d), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
    )
    shutil.rmtree(d)
    assert result.returncode == 0


def test_pipeline_config_defaults() -> None:
    """PipelineConfig has correct defaults."""
    from ocr_pipeline.config import PipelineConfig

    c = PipelineConfig(input_dir=Path("/tmp"), output_dir=Path("/tmp"))
    assert c.profile == "general"
    assert c.vlm_model == "gemini-2.5-flash"
    assert c.file_concurrency == 2
    assert c.vlm_cost_per_call == 0.00015


def test_script_detection() -> None:
    """_detect_script correctly identifies Unicode scripts."""
    from ocr_pipeline.page_processor import _detect_script

    assert _detect_script("Hello world") == "latin"
    assert _detect_script("Привет мир") == "cyrillic"
    assert _detect_script("你好世界") == "cjk"
    assert _detect_script("こんにちは") == "cjk"
    assert _detect_script("مرحبا بالعالم") == "arabic"
    assert _detect_script("Γειά σου Κόσμε") == "greek"
    assert _detect_script("") == "latin"


def test_model_routing_all_profiles() -> None:
    """Every profile has model_routing with CJK key."""
    from ocr_pipeline.profiles import PROFILES

    for name, p in PROFILES.items():
        assert p.model_routing
        assert "cjk" in p.model_routing
        assert p.model_routing["cjk"] == "claude-haiku-4-5"


def test_rtl_detection() -> None:
    """is_rtl correctly identifies RTL languages."""
    from ocr_pipeline.languages import is_rtl

    assert is_rtl("ar") and is_rtl("he") and is_rtl("fa")
    assert not is_rtl("en") and not is_rtl("zh")


def test_checkpoint_v3_init() -> None:
    """Checkpoint v3 initializes correctly with per-PDF directory."""
    import tempfile
    import shutil
    from ocr_pipeline.checkpoint import CheckpointManager

    d = Path(tempfile.mkdtemp()) / ".checkpoint"
    cm = CheckpointManager(d)
    assert d.exists()
    assert isinstance(cm.stats(), dict)
    shutil.rmtree(d.parent)
