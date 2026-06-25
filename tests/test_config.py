"""Tests for PipelineConfig and ConfigLoader."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ocr_pipeline.config import ConfigLoader, PipelineConfig
from ocr_pipeline.errors import ConfigError


# ---------------------------------------------------------------------------
# PipelineConfig defaults
# ---------------------------------------------------------------------------


class TestPipelineConfigDefaults:
    def test_default_engines(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert cfg.engines == ["marker"]

    def test_default_vlm(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert cfg.vlm_enabled is True
        assert cfg.vlm_model == "gemini-3.5-flash"
        assert cfg.vlm_fallback_model == "claude-sonnet-4-6"

    def test_default_postprocess(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert cfg.postprocess_enabled is True
        assert cfg.postprocess_steps == [
            "soft_hyphens",
            "em_dash_breaks",
            "whitespace_normalize",
            "ligature_expand",
            "stray_control_chars",
        ]

    def test_default_retry(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert cfg.max_retries == 3
        assert cfg.retry_base_delay_sec == 1.0
        assert cfg.retry_max_delay_sec == 60.0

    def test_default_concurrency(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert cfg.max_workers == 4
        assert cfg.marker_concurrency == 1

    def test_default_budget(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert cfg.budget_cap_usd is None

    def test_default_output_formats(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert cfg.output_formats == ["markdown"]

    def test_required_fields(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert isinstance(cfg.input_dir, Path)
        assert isinstance(cfg.output_dir, Path)
        assert str(cfg.input_dir) == "/in"


# ---------------------------------------------------------------------------
# ConfigLoader._flatten_dict
# ---------------------------------------------------------------------------


class TestFlattenDict:
    def test_flat_yaml_unchanged(self):
        raw = {"engines": ["marker"], "render_dpi": 300}
        result = ConfigLoader._flatten_dict(raw)
        assert result["engines"] == ["marker"]
        assert result["render_dpi"] == 300

    def test_nested_vlm_section_unpacked(self):
        raw = {"vlm": {"enabled": False, "model": "gemini-pro"}}
        result = ConfigLoader._flatten_dict(raw)
        assert result["vlm_enabled"] is False
        assert result["vlm_model"] == "gemini-pro"
        assert "vlm" in result  # original key preserved

    def test_nested_postprocess_section_unpacked(self):
        raw = {"postprocess": {"enabled": False, "steps": ["ligature_expand"]}}
        result = ConfigLoader._flatten_dict(raw)
        assert result["postprocess_enabled"] is False
        assert result["postprocess_steps"] == ["ligature_expand"]

    def test_nested_retry_section_unpacked(self):
        raw = {"retry": {"max_retries": 5, "base_delay_sec": 2.0}}
        result = ConfigLoader._flatten_dict(raw)
        assert result["retry_max_retries"] == 5
        assert result["retry_base_delay_sec"] == 2.0

    def test_multiple_nested_sections(self):
        raw = {
            "vlm": {"enabled": True},
            "postprocess": {"enabled": False},
            "engines": ["marker"],
        }
        result = ConfigLoader._flatten_dict(raw)
        assert result["vlm_enabled"] is True
        assert result["postprocess_enabled"] is False
        assert result["engines"] == ["marker"]


# ---------------------------------------------------------------------------
# ConfigLoader._from_dict
# ---------------------------------------------------------------------------


class TestFromDict:
    def test_basic_config(self):
        raw: dict[str, object] = {
            "input_dir": "/tmp/in",
            "output_dir": "/tmp/out",
            "engines": ["marker", "mathpix"],
        }
        cfg = ConfigLoader._from_dict(raw)
        assert cfg.input_dir == Path("/tmp/in")
        assert cfg.output_dir == Path("/tmp/out")
        assert cfg.engines == ["marker", "mathpix"]

    def test_missing_required_input_dir_raises(self):
        raw: dict[str, object] = {"output_dir": "/tmp/out"}
        with pytest.raises(ConfigError, match="input_dir"):
            ConfigLoader._from_dict(raw)  # type: ignore[arg-type]

    def test_missing_required_output_dir_raises(self):
        raw: dict[str, object] = {"input_dir": "/tmp/in"}
        with pytest.raises(ConfigError, match="output_dir"):
            ConfigLoader._from_dict(raw)  # type: ignore[arg-type]

    def test_optional_checkpoint_dir(self):
        raw: dict[str, object] = {
            "input_dir": "/in",
            "output_dir": "/out",
            "checkpoint_dir": "/tmp/ckpt",
        }
        cfg = ConfigLoader._from_dict(raw)
        assert cfg.checkpoint_dir == Path("/tmp/ckpt")

    def test_optional_checkpoint_dir_empty_is_none(self):
        raw: dict[str, object] = {
            "input_dir": "/in",
            "output_dir": "/out",
            "checkpoint_dir": "",
        }
        cfg = ConfigLoader._from_dict(raw)
        assert cfg.checkpoint_dir is None


# ---------------------------------------------------------------------------
# ConfigLoader.from_yaml
# ---------------------------------------------------------------------------


class TestFromYaml:
    def test_basic_yaml(self):
        yaml_content = "input_dir: /foo\noutput_dir: /bar\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            cfg = ConfigLoader.from_yaml(Path(f.name))
        assert cfg.input_dir == Path("/foo")
        assert cfg.output_dir == Path("/bar")

    def test_nested_yaml(self):
        yaml_content = (
            "input_dir: /a\n"
            "output_dir: /b\n"
            "vlm:\n"
            "  enabled: false\n"
            "  model: my-model\n"
            "postprocess:\n"
            "  steps:\n"
            "    - soft_hyphens\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            cfg = ConfigLoader.from_yaml(Path(f.name))
        assert cfg.vlm_enabled is False
        assert cfg.vlm_model == "my-model"
        assert cfg.postprocess_steps == ["soft_hyphens"]

    def test_missing_file_raises_config_error(self):
        with pytest.raises(ConfigError, match="Config file not found"):
            ConfigLoader.from_yaml(Path("/nonexistent/config.yaml"))

    def test_empty_yaml_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            with pytest.raises(ConfigError, match="input_dir"):
                ConfigLoader.from_yaml(Path(f.name))

    def test_missing_input_dir_in_yaml_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("output_dir: /only_out\n")
            f.flush()
            with pytest.raises(ConfigError, match="input_dir"):
                ConfigLoader.from_yaml(Path(f.name))


# ---------------------------------------------------------------------------
# ConfigLoader.from_env
# ---------------------------------------------------------------------------


class TestFromEnv:
    def test_required_env_vars(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/env/in")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/env/out")
        cfg = ConfigLoader.from_env()
        assert cfg.input_dir == Path("/env/in")
        assert cfg.output_dir == Path("/env/out")

    def test_missing_input_dir_raises(self, monkeypatch):
        monkeypatch.delenv("OCR_PIPELINE_INPUT_DIR", raising=False)
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/env/out")
        with pytest.raises(ConfigError, match="OCR_PIPELINE_INPUT_DIR"):
            ConfigLoader.from_env()

    def test_missing_output_dir_raises(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/env/in")
        monkeypatch.delenv("OCR_PIPELINE_OUTPUT_DIR", raising=False)
        with pytest.raises(ConfigError, match="OCR_PIPELINE_OUTPUT_DIR"):
            ConfigLoader.from_env()

    def test_budget_cap_from_env(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/in")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/out")
        monkeypatch.setenv("OCR_PIPELINE_BUDGET_CAP_USD", "42.50")
        cfg = ConfigLoader.from_env()
        assert cfg.budget_cap_usd == 42.50

    def test_engines_comma_separated(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/in")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/out")
        monkeypatch.setenv("OCR_PIPELINE_ENGINES", "marker,mathpix,surya2")
        cfg = ConfigLoader.from_env()
        assert cfg.engines == ["marker", "mathpix", "surya2"]

    def test_output_formats_comma_separated(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/in")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/out")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_FORMATS", "markdown,json")
        cfg = ConfigLoader.from_env()
        assert cfg.output_formats == ["markdown", "json"]

    def test_vlm_enabled_true(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/in")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/out")
        monkeypatch.setenv("OCR_PIPELINE_VLM_ENABLED", "true")
        cfg = ConfigLoader.from_env()
        assert cfg.vlm_enabled is True

    def test_vlm_enabled_false(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/in")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/out")
        monkeypatch.setenv("OCR_PIPELINE_VLM_ENABLED", "0")
        cfg = ConfigLoader.from_env()
        assert cfg.vlm_enabled is False

    def test_int_values(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/in")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/out")
        monkeypatch.setenv("OCR_PIPELINE_MAX_WORKERS", "8")
        monkeypatch.setenv("OCR_PIPELINE_RENDER_DPI", "600")
        monkeypatch.setenv("OCR_PIPELINE_MAX_RETRIES", "5")
        cfg = ConfigLoader.from_env()
        assert cfg.max_workers == 8
        assert cfg.render_dpi == 600
        assert cfg.max_retries == 5


# ---------------------------------------------------------------------------
# PipelineConfig._resolve_marker_venv
# ---------------------------------------------------------------------------


class TestResolveMarkerVenv:
    def test_none_stays_none(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"), marker_venv=None)
        cfg._resolve_marker_venv(None)
        assert cfg.marker_venv is None

    def test_empty_string_becomes_none(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"), marker_venv="")
        cfg._resolve_marker_venv(None)
        assert cfg.marker_venv is None

    def test_relative_path_resolved_against_config_dir(self):
        cfg = PipelineConfig(
            input_dir=Path("/in"),
            output_dir=Path("/out"),
            marker_venv="marker_env/bin/python",
        )
        cfg._resolve_marker_venv(Path("/config/dir"))
        assert cfg.marker_venv is not None
        assert "marker_env/bin/python" in cfg.marker_venv
        assert cfg.marker_venv.startswith("/config/dir/")

    def test_relative_path_without_config_dir_becomes_none(self):
        cfg = PipelineConfig(
            input_dir=Path("/in"),
            output_dir=Path("/out"),
            marker_venv="relative/path",
        )
        cfg._resolve_marker_venv(None)
        assert cfg.marker_venv is None

    def test_absolute_path_preserved(self):
        cfg = PipelineConfig(
            input_dir=Path("/in"),
            output_dir=Path("/out"),
            marker_venv="/absolute/path/to/python",
        )
        cfg._resolve_marker_venv(Path("/config"))
        assert cfg.marker_venv == "/absolute/path/to/python"


# ---------------------------------------------------------------------------
# output_formats parsing
# ---------------------------------------------------------------------------


class TestOutputFormatsParsing:
    def test_default_is_markdown(self):
        cfg = PipelineConfig(input_dir=Path("/in"), output_dir=Path("/out"))
        assert cfg.output_formats == ["markdown"]

    def test_env_var_comma_separated(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/in")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/out")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_FORMATS", "json,csv,markdown")
        cfg = ConfigLoader.from_env()
        assert cfg.output_formats == ["json", "csv", "markdown"]

    def test_env_var_single_value(self, monkeypatch):
        monkeypatch.setenv("OCR_PIPELINE_INPUT_DIR", "/in")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_DIR", "/out")
        monkeypatch.setenv("OCR_PIPELINE_OUTPUT_FORMATS", "json")
        cfg = ConfigLoader.from_env()
        assert cfg.output_formats == ["json"]
