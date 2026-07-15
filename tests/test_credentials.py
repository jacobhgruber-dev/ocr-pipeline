"""Tests for the centralized credential resolver."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from ocr_pipeline.credentials import (
    _find_project_root,
    _opencode_cache,
    _read_opencode_credential,
    _read_yaml_credential,
    _yaml_cache,
    resolve_credential,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, content: dict) -> None:
    import yaml

    path.write_text(yaml.dump(content), encoding="utf-8")


def _write_json(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content), encoding="utf-8")


# ---------------------------------------------------------------------------
# Source 1: os.environ
# ---------------------------------------------------------------------------


def test_resolve_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TEST_KEY", "env-value")
    assert resolve_credential("MY_TEST_KEY") == "env-value"


# ---------------------------------------------------------------------------
# Source 2: config.yaml
# ---------------------------------------------------------------------------


def test_resolve_from_yaml_credentials_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Key found under credentials: section."""
    monkeypatch.delenv("TEST_KEY", raising=False)
    cfg = tmp_path / "config.yaml"
    _write_yaml(cfg, {"credentials": {"TEST_KEY": "yaml-cred-val"}})

    result = resolve_credential("TEST_KEY", config_yaml_paths=[cfg])
    assert result == "yaml-cred-val"


def test_resolve_from_yaml_top_level(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Key found as a top-level key (backwards compat)."""
    monkeypatch.delenv("TEST_KEY", raising=False)
    cfg = tmp_path / "config.yaml"
    _write_yaml(cfg, {"TEST_KEY": "flat-val"})

    result = resolve_credential("TEST_KEY", config_yaml_paths=[cfg])
    assert result == "flat-val"


def test_resolve_from_yaml_credentials_beats_top_level(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both ``credentials.TEST_KEY`` and top-level ``TEST_KEY`` exist —
    the credentials section wins."""
    monkeypatch.delenv("TEST_KEY", raising=False)
    cfg = tmp_path / "config.yaml"
    _write_yaml(cfg, {"credentials": {"TEST_KEY": "from-creds"}, "TEST_KEY": "from-top"})

    result = resolve_credential("TEST_KEY", config_yaml_paths=[cfg])
    assert result == "from-creds"


# ---------------------------------------------------------------------------
# Source 3: opencode.json
# ---------------------------------------------------------------------------


def test_resolve_from_opencode_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """credentials.{key} in opencode.json."""
    monkeypatch.delenv("TEST_KEY", raising=False)

    oc_dir = tmp_path / ".config" / "opencode"
    oc_dir.mkdir(parents=True, exist_ok=True)
    oc = oc_dir / "opencode.json"
    _write_json(oc, {"credentials": {"TEST_KEY": "oc-cred-val"}})

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("TEST_KEY", config_yaml_paths=[])
        assert result == "oc-cred-val"


def test_resolve_from_opencode_provider_google(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """provider.google.options.apiKey → GEMINI_API_KEY."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    oc_dir = tmp_path / ".config" / "opencode"
    oc_dir.mkdir(parents=True, exist_ok=True)
    oc = oc_dir / "opencode.json"
    _write_json(oc, {"provider": {"google": {"options": {"apiKey": "google-key-123"}}}})

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("GEMINI_API_KEY", config_yaml_paths=[])
        assert result == "google-key-123"


def test_resolve_from_opencode_provider_anthropic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """provider.anthropic.options.apiKey → ANTHROPIC_API_KEY."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    oc_dir = tmp_path / ".config" / "opencode"
    oc_dir.mkdir(parents=True, exist_ok=True)
    oc = oc_dir / "opencode.json"
    _write_json(oc, {"provider": {"anthropic": {"options": {"apiKey": "anthro-secret"}}}})

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("ANTHROPIC_API_KEY", config_yaml_paths=[])
        assert result == "anthro-secret"


def test_resolve_from_opencode_provider_mathpix_app_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """provider.mathpix.options.appId → MATHPIX_APP_ID."""
    monkeypatch.delenv("MATHPIX_APP_ID", raising=False)

    oc_dir = tmp_path / ".config" / "opencode"
    oc_dir.mkdir(parents=True, exist_ok=True)
    oc = oc_dir / "opencode.json"
    _write_json(oc, {"provider": {"mathpix": {"options": {"appId": "my-app-id"}}}})

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("MATHPIX_APP_ID", config_yaml_paths=[])
        assert result == "my-app-id"


def test_resolve_from_opencode_provider_mathpix_app_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """provider.mathpix.options.appKey → MATHPIX_APP_KEY."""
    monkeypatch.delenv("MATHPIX_APP_KEY", raising=False)

    oc_dir = tmp_path / ".config" / "opencode"
    oc_dir.mkdir(parents=True, exist_ok=True)
    oc = oc_dir / "opencode.json"
    _write_json(oc, {"provider": {"mathpix": {"options": {"appKey": "my-app-key"}}}})

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("MATHPIX_APP_KEY", config_yaml_paths=[])
        assert result == "my-app-key"


def test_resolve_from_opencode_mcp_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """mcp.ocr-pipeline.environment.TEST_KEY."""
    monkeypatch.delenv("TEST_KEY", raising=False)

    oc_dir = tmp_path / ".config" / "opencode"
    oc_dir.mkdir(parents=True, exist_ok=True)
    oc = oc_dir / "opencode.json"
    _write_json(oc, {"mcp": {"ocr-pipeline": {"environment": {"TEST_KEY": "mcp-env-val"}}}})

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("TEST_KEY", config_yaml_paths=[])
        assert result == "mcp-env-val"


def test_resolve_from_opencode_mcp_env_alt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """mcp.ocr-pipeline.env.TEST_KEY (alternate key name)."""
    monkeypatch.delenv("TEST_KEY", raising=False)

    oc_dir = tmp_path / ".config" / "opencode"
    oc_dir.mkdir(parents=True, exist_ok=True)
    oc = oc_dir / "opencode.json"
    _write_json(oc, {"mcp": {"ocr-pipeline": {"env": {"TEST_KEY": "mcp-env-alt"}}}})

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("TEST_KEY", config_yaml_paths=[])
        assert result == "mcp-env-alt"


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


def test_resolve_priority_env_beats_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Env var beats both config.yaml and opencode.json."""
    monkeypatch.setenv("PRI_KEY", "env-priority")

    # YAML
    cfg = tmp_path / "config.yaml"
    _write_yaml(cfg, {"credentials": {"PRI_KEY": "yaml-val"}})

    # opencode
    oc_dir = tmp_path / ".config" / "opencode"
    oc_dir.mkdir(parents=True, exist_ok=True)
    oc = oc_dir / "opencode.json"
    _write_json(oc, {"credentials": {"PRI_KEY": "oc-val"}})

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("PRI_KEY", config_yaml_paths=[cfg])
        assert result == "env-priority"


def test_resolve_priority_yaml_beats_opencode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """config.yaml beats opencode.json when env is unset."""
    monkeypatch.delenv("PRI_KEY", raising=False)

    cfg = tmp_path / "config.yaml"
    _write_yaml(cfg, {"credentials": {"PRI_KEY": "yaml-priority"}})

    oc_dir = tmp_path / ".config" / "opencode"
    oc_dir.mkdir(parents=True, exist_ok=True)
    oc = oc_dir / "opencode.json"
    _write_json(oc, {"credentials": {"PRI_KEY": "oc-val"}})

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("PRI_KEY", config_yaml_paths=[cfg])
        assert result == "yaml-priority"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_resolve_unconfigured_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """No source has the key — returns empty string."""
    monkeypatch.delenv("NOT_SET_KEY", raising=False)

    # Clear caches so we don't pick up leftover data from other tests.
    _yaml_cache.clear()
    _opencode_cache.clear()

    # Mock Path.home so we don't read the developer's real opencode.json.
    with mock.patch.object(Path, "home", return_value=Path("/nonexistent/home")):
        result = resolve_credential("NOT_SET_KEY", config_yaml_paths=[Path("/nonexistent/config.yaml")])
    assert result == ""


def test_missing_files_dont_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither config.yaml nor opencode.json exist — returns empty string."""
    monkeypatch.delenv("ANY_KEY", raising=False)
    _yaml_cache.clear()

    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_credential("ANY_KEY", config_yaml_paths=[tmp_path / "no_such.yaml"])
    assert result == ""


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------


def test_cache_invalidation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Modifying a config.yaml changes its mtime → cache misses → re-reads."""
    monkeypatch.delenv("CACHE_KEY", raising=False)
    _yaml_cache.clear()

    cfg = tmp_path / "config.yaml"
    _write_yaml(cfg, {"credentials": {"CACHE_KEY": "first-val"}})

    # 1st read
    result1 = resolve_credential("CACHE_KEY", config_yaml_paths=[cfg])
    assert result1 == "first-val"

    # Verify cached
    assert cfg in _yaml_cache

    # Mutate the file (change mtime)
    _write_yaml(cfg, {"credentials": {"CACHE_KEY": "second-val"}})

    # 2nd read — should see the new value
    result2 = resolve_credential("CACHE_KEY", config_yaml_paths=[cfg])
    assert result2 == "second-val"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_find_project_root() -> None:
    """_find_project_root() locates the directory with pyproject.toml."""
    root = _find_project_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "ocr_pipeline" / "credentials.py").is_file()


def test_read_yaml_credential_nonexistent_paths() -> None:
    """_read_yaml_credential with a non-existent file returns ''."""
    result = _read_yaml_credential("ANY_KEY", [Path("/nonexistent/for/sure.yaml")])
    assert result == ""


def test_read_opencode_credential_no_file(tmp_path: Path) -> None:
    """_read_opencode_credential returns '' when opencode.json does not exist."""
    import ocr_pipeline.credentials as cred_mod

    cred_mod._opencode_cache.clear()
    with mock.patch.object(Path, "home", return_value=tmp_path):
        result = _read_opencode_credential("ANY_KEY")
    assert result == ""
