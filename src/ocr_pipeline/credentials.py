"""Centralized credential resolver.

Replaces ``CredentialStore`` with a single ``resolve_credential()`` function
that searches a priority-ordered chain of sources.

Priority (first non-empty value wins):
1. ``os.environ[key]``
2. ``config.yaml`` → ``credentials:`` section, then top-level flat keys
3. ``~/.config/opencode/opencode.json`` → credentials / provider.* / mcp.*
4. ``""`` (unconfigured)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level caches (invalidated by file mtime)
# ---------------------------------------------------------------------------

_yaml_cache: dict[Path, tuple[float, dict[str, Any]]] = {}
"""Mapping of YAML path → (mtime, parsed dict)."""

_opencode_cache: dict[Path, tuple[float, dict[str, Any]]] = {}
"""Mapping of opencode.json path → (mtime, parsed dict)."""

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Walk up from this source file until ``pyproject.toml`` is found."""
    current = Path(__file__).resolve().parent
    for _ in range(12):
        if (current / "pyproject.toml").is_file():
            return current
        if current.parent == current:
            break
        current = current.parent
    raise FileNotFoundError("Could not locate pyproject.toml (project root)")


def _resolve_yaml_candidates(paths: list[Path] | None) -> list[Path]:
    """Build the ordered list of YAML config file paths to try."""
    if paths is not None:
        return list(paths)

    candidates: list[Path] = [Path("config.yaml")]
    try:
        root = _find_project_root()
    except FileNotFoundError:
        return candidates
    if root != Path.cwd():
        candidates.append(root / "config.yaml")
    return candidates


# ---------------------------------------------------------------------------
# Cache / load helpers
# ---------------------------------------------------------------------------


def _str_value(obj: object) -> str | None:
    """Return *obj* as a non-empty string, or ``None``."""
    if isinstance(obj, str) and obj:
        return obj
    return None


def _load_yaml(path: Path) -> dict[str, Any] | None:
    """Read and parse *path* as YAML, using the mtime-based cache.

    Returns the parsed dict on success, or ``None`` if the file cannot
    be read or parsed.
    """
    if not path.is_file():
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    cached = _yaml_cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        import yaml
    except ImportError:
        logger.info("PyYAML not available — skipping %s", path)
        return None

    with open(path) as fh:
        raw = yaml.safe_load(fh)
    data: dict[str, Any] = raw if isinstance(raw, dict) else {}
    _yaml_cache[path] = (mtime, data)
    return data


def _load_opencode(path: Path) -> dict[str, Any] | None:
    """Read and parse *path* as JSON, using the mtime-based cache.

    Returns the parsed dict on success, or ``None`` if the file cannot
    be read or parsed.
    """
    if not path.is_file():
        _opencode_cache.pop(path, None)
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:
        _opencode_cache.pop(path, None)
        return None

    cached = _opencode_cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse %s", path, exc_info=True)
        _opencode_cache.pop(path, None)
        return None
    if not isinstance(data, dict):
        _opencode_cache.pop(path, None)
        return None
    _opencode_cache[path] = (mtime, data)
    return data


# ---------------------------------------------------------------------------
# OpenCode JSON section readers
# ---------------------------------------------------------------------------

# Provider-to-standard-key mapping used by the credential resolver.
_PROVIDER_MAP: dict[str, dict[str, str]] = {
    "google": {"apiKey": "GEMINI_API_KEY"},
    "anthropic": {"apiKey": "ANTHROPIC_API_KEY"},
    "mathpix": {"appId": "MATHPIX_APP_ID", "appKey": "MATHPIX_APP_KEY"},
    "xai": {"apiKey": "XAI_API_KEY"},
    "grok": {"apiKey": "XAI_API_KEY"},
}


def _resolve_from_providers(data: dict[str, Any], key: str) -> str:
    """Look up *key* under ``provider.<name>.options.<field>``."""
    providers = data.get("provider")
    if not isinstance(providers, dict):
        return ""
    for prov_name, field_map in _PROVIDER_MAP.items():
        prov = providers.get(prov_name)
        if not isinstance(prov, dict):
            continue
        opts = prov.get("options")
        if not isinstance(opts, dict):
            continue
        for src_field, target_key in field_map.items():
            if target_key != key:
                continue
            val = _str_value(opts.get(src_field))
            if val is not None:
                logger.debug(
                    "%s resolved from opencode.json provider.%s.options.%s",
                    key, prov_name, src_field,
                )
                return val
    return ""


def _resolve_from_mcp(data: dict[str, Any], key: str) -> str:
    """Look up *key* under ``mcp.ocr-pipeline.environment`` or ``.env``."""
    mcp = data.get("mcp")
    if not isinstance(mcp, dict):
        return ""
    ocr_cfg = mcp.get("ocr-pipeline")
    if not isinstance(ocr_cfg, dict):
        return ""
    env = ocr_cfg.get("environment") or ocr_cfg.get("env")
    if not isinstance(env, dict):
        return ""
    val = _str_value(env.get(key))
    if val is not None:
        logger.debug("%s resolved from opencode.json mcp.ocr-pipeline.environment.%s", key, key)
        return val
    return ""


# ---------------------------------------------------------------------------
# Source 2 & 3 resolvers
# ---------------------------------------------------------------------------


def _read_yaml_credential(key: str, paths: list[Path] | None) -> str:
    """Read *key* from one or more YAML config files.

    For each file: ``credentials.*key*`` first, then top-level ``*key*``.
    """
    for path in _resolve_yaml_candidates(paths):
        data = _load_yaml(path)
        if data is None:
            continue

        # 1) credentials section
        creds = data.get("credentials")
        if isinstance(creds, dict):
            val = _str_value(creds.get(key))
            if val is not None:
                logger.debug("%s resolved from config.yaml credentials.%s (%s)", key, key, path)
                return val

        # 2) top-level flat key (backwards compat)
        val = _str_value(data.get(key))
        if val is not None:
            logger.debug("%s resolved from config.yaml top-level key (%s)", key, path)
            return val

    return ""


def _read_opencode_credential(key: str) -> str:
    """Read *key* from ``~/.config/opencode/opencode.json``."""
    path = Path.home() / ".config" / "opencode" / "opencode.json"
    data = _load_opencode(path)
    if data is None:
        return ""

    # 1) credentials section
    creds = data.get("credentials")
    if isinstance(creds, dict):
        val = _str_value(creds.get(key))
        if val is not None:
            logger.debug("%s resolved from opencode.json credentials.%s", key, key)
            return val

    # 2) provider.*.options mapping
    val = _resolve_from_providers(data, key)
    if val:
        return val

    # 3) mcp.ocr-pipeline.environment / .env
    return _resolve_from_mcp(data, key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_credential(key: str, config_yaml_paths: list[Path] | None = None) -> str:
    """Resolve a credential from all available sources.

    Priority (first non-empty value wins):
    1. ``os.environ[key]``
    2. ``config.yaml`` → ``credentials:`` section, then top-level flat keys
    3. ``~/.config/opencode/opencode.json`` → nested credential storage
    4. ``""`` (unconfigured)

    Args:
        key: The credential key to look up (e.g. ``"GEMINI_API_KEY"``).
        config_yaml_paths: Optional list of YAML config files to try.
            When ``None``, ``Path("config.yaml")`` is tried first, then
            ``<project-root>/config.yaml``.

    Returns:
        The credential value as a string, or ``""`` if unconfigured.
    """
    # 1) Environment
    val = os.environ.get(key, "")
    if val:
        logger.debug("%s resolved from os.environ", key)
        return val

    # 2) config.yaml
    val = _read_yaml_credential(key, config_yaml_paths)
    if val:
        return val

    # 3) opencode.json
    val = _read_opencode_credential(key)
    if val:
        return val

    # 4) Unconfigured
    logger.debug("%s unconfigured (no source had the key)", key)
    return ""
