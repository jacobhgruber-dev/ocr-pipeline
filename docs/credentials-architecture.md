# Credential Consolidation — Architectural Plan

## Summary

Create a single `credentials.py` module with a `resolve_credential(key)` function that replaces all 4 current resolution chains. Every consumer — engines, merger, MCP, CLI — routes through this one function. The priority order is unambiguous and documented in one place: `os.environ > config.yaml > opencode.json`. Delete `CredentialStore`, remove dead PipelineConfig fields, add the two missing ones (`google_api_key`, `xai_api_key`), and update `config.example.yaml`.

## Mode

**Fresh first-principles design** for the credential resolution layer; **refactor scoping** for the consumers.

## Design Forces

1. **User's explicit goal**: shift toward shell environment variables (`~/.zshrc`, etc.) as the primary credential source, instead of relying on config files passed to the MCP.
2. **MCP process boundary**: MCP servers do NOT inherit the user's shell environment. The user must set env vars in `opencode.json`'s `mcp.ocr-pipeline.environment` section (which opencode passes to the MCP process as actual environment variables). This means `os.environ` will contain the right values in both CLI and MCP contexts — IF the user configures it that way.
3. **Backward compatibility**: `config.yaml` is still used by non-opencode users and CI pipelines. It must remain a supported source.
4. **opencode.json integration**: The `credentials` section in `~/.config/opencode/opencode.json` is a useful shared credential store across opencode tools. Keep it as a fallback, not as a primary path.
5. **Consistency**: Today, the same credential can resolve differently depending on which code path calls it (MathpixEngine vs create_engine, merger vs metadata). This is the root problem to fix.

## Current State Audit (Foundation for the Plan)

### 8 credentials, 4 resolution paths

| Credential | Path 1: CredentialStore (engines + merger) | Path 2: PipelineConfig fields (from_yaml/from_env) | Path 3: create_engine factory | Path 4: hardcoded os.environ.get() |
|---|---|---|---|---|
| `GEMINI_API_KEY` | CredentialStore.get() in merger.py _call_gemini (line 292) | PipelineConfig.gemini_api_key (read by Pipeline → metadata_vlm) | — | VlmMetadataEngine.__init__ (line 110) |
| `ANTHROPIC_API_KEY` | CredentialStore.get() in merger.py _call_anthropic (line 180) | PipelineConfig.anthropic_api_key (**dead** — merger ignores it) | — | — |
| `MATHPIX_APP_ID` | CredentialStore.get() in MathpixEngine.__init__ (line 31) | PipelineConfig.mathpix_app_id | create_engine → config.mathpix_app_id then os.environ.get() (lines 104-107) | — |
| `MATHPIX_APP_KEY` | CredentialStore.get() in MathpixEngine.__init__ (line 32) | PipelineConfig.mathpix_app_key | create_engine → config.mathpix_app_key then os.environ.get() (lines 108-109) | — |
| `GOOGLE_CLOUD_PROJECT` | — | PipelineConfig.google_cloud_project | create_engine → config field then os.environ.get() (line 122) | — |
| `GOOGLE_API_KEY` | — | **No PipelineConfig field** | — | GoogleDocAiEngine._get_client() line 46 |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | PipelineConfig field (**dead** — SDK reads env directly) | — | Google SDK reads it from env automatically |
| `XAI_API_KEY` | — | **No PipelineConfig field** | — | merger.py _call_grok() line 379 |

### CredentialStore internals (base.py lines 203-315)

Reads 4 sources in this order (per its docstring: env var > opencode global > opencode project > legacy config.yaml). But its `get()` method actually does `os.environ.get(key) or self._data.get(key)` — env vars checked FIRST, then all file sources as fallback. Within file sources: opencode global → opencode project → legacy YAML (first non-empty value wins).

The opencode integration is clever: it reads `credentials.*`, `provider.*.options`, and `mcp.*.environment/env` from the JSON. This means credentials can be set at 3 different locations in opencode.json and CredentialStore will find them.

## Approaches Considered

### Option A: Centralized `resolve_credential()` function (RECOMMENDED)

Create `src/ocr_pipeline/credentials.py` with a module-level function:

```python
def resolve_credential(key: str, config: PipelineConfig | None = None) -> str:
    """Single credential resolver for ALL code paths.
    
    Priority (first non-empty value wins):
    1. os.environ[key]
    2. config.yaml → credentials section (project root)
    3. ~/.config/opencode/opencode.json (credentials, provider, mcp sections)
    4. Empty string (unconfigured)
    """
```

Every consumer calls this. Delete `CredentialStore` class.

**Pros:**
- ONE resolution path, no divergence possible
- Trivially auditable — grep for `resolve_credential` finds all credential usage
- No new abstractions — a function, not a class with state
- Dead simple to test
- Consumers that have PipelineConfig can pass it for YAML-backed resolution; consumers without it (merger) just call `resolve_credential("GEMINI_API_KEY")` and get env var + opencode fallback

**Cons:**
- `config.yaml` reading happens once per call (mitigated: YAML is tiny, and we can add a module-level cache)
- PipelineConfig fields become documentation-only (YAML values flow through config.yaml file, not through PipelineConfig.gemini_api_key attributes)

### Option B: PipelineConfig as credential hub

Add a `resolve_credential(key)` method to PipelineConfig that reads its own fields first, then env vars as overrides, then opencode.json. All consumers get a PipelineConfig reference.

**Pros:**
- PipelineConfig becomes the single source of truth
- Config fields are actively used, not just documentation

**Cons:**
- The merger (`_call_gemini`, `_call_anthropic`, `_call_grok`) has NO PipelineConfig reference. Threading it through the call chain (Pipeline → PageProcessor → DefaultVlmMerger.merge → merge_with_vlm → _call_gemini) requires changing the `VlmMerger` Protocol signature. That's a breaking change to the merger abstraction.
- Forces PipelineConfig into code paths that don't need it otherwise
- More invasive refactor

### Option C: Keep CredentialStore, just fix consumers

Keep the CredentialStore class but ensure every consumer uses it. Add missing keys (`GOOGLE_API_KEY`, `XAI_API_KEY`) to the `provider.*.options` map.

**Pros:**
- Smallest code change
- Preserves the opencode.json integration intact

**Cons:**
- CredentialStore still has internal mutation (self._data dict, first-write-wins semantics)
- Still TWO parallel systems (PipelineConfig fields + CredentialStore)
- The opencode.json integration remains opaque — you have to read CredentialStore internals to understand what it reads
- Doesn't address the user's stated goal of shifting toward env vars (CredentialStore already puts env vars first, but the problem is fragmentation, not ordering)

## Recommendation: Option A

**Why:**
1. It addresses the root problem (fragmentation), not just the symptoms
2. It's the simplest approach that guarantees consistency
3. It requires zero changes to the `VlmMerger` protocol
4. The function signature is self-documenting: `resolve_credential(key, config=None)` tells you exactly what sources are used
5. It's trivial to add logging/debugging to trace which source resolved each credential
6. PipelineConfig fields remain for backward-compatible property-style access if needed later (a property that delegates to `resolve_credential`), but they don't need to be the resolution mechanism itself

### What the codebase looks like after

```
src/ocr_pipeline/
├── credentials.py          ← NEW: resolve_credential() + opencode.json reader
├── config.py               ← MODIFIED: add google_api_key, xai_api_key fields;
│                              remove google_application_credentials;
│                              remove CredentialStore import from engines/__init__
├── engines/
│   ├── base.py             ← MODIFIED: DELETE CredentialStore class (lines 203-315)
│   ├── __init__.py         ← MODIFIED: remove CredentialStore import/export;
│                              replace os.environ.get() with resolve_credential()
│   ├── google_doc_ai.py    ← MODIFIED: replace os.environ.get("GOOGLE_API_KEY")
│   ├── mathpix.py          ← MODIFIED: replace CredentialStore usage
│   └── metadata_vlm.py     ← MODIFIED: replace os.environ.get("GEMINI_API_KEY")
├── merger.py               ← MODIFIED: replace CredentialStore + os.environ
│                              with resolve_credential() in _call_gemini,
│                              _call_anthropic, _call_grok
└── mcp_server.py           ← MODIFIED: remove apply_env_credentials() call
                               (no longer needed — consumers resolve their own)
config.example.yaml         ← MODIFIED: add google_api_key, xai_api_key;
                               remove google_application_credentials;
                               add credentials: section consistent with resolver
```

### Resolution priority (documented in credentials.py docstring)

```
1. os.environ[key]                    ← from shell (.zshrc), MCP environment, or CI
2. config.yaml → credentials section  ← project-level explicit config
3. opencode.json → credentials        ← shared opencode credential store (deep fallback)
4. ""                                 ← unconfigured (consumer handles gracefully)
```

**Why config.yaml before opencode.json?** For CLI usage, the user explicitly creates config.yaml when they want file-based config. For MCP usage, env vars are injected by opencode (priority 1). opencode.json is the "deep fallback" for when nothing else is set — it's the least transparent and most tightly coupled to opencode.

**For MCP users who want env-var-based config:** Set env vars in `~/.config/opencode/opencode.json` under:
```json
{
  "mcp": {
    "ocr-pipeline": {
      "environment": {
        "GEMINI_API_KEY": "xxx",
        "ANTHROPIC_API_KEY": "xxx",
        "MATHPIX_APP_ID": "xxx",
        "MATHPIX_APP_KEY": "xxx",
        "GOOGLE_CLOUD_PROJECT": "xxx",
        "GOOGLE_API_KEY": "xxx",
        "XAI_API_KEY": "xxx"
      }
    }
  }
}
```
These are injected as real environment variables by opencode, so `os.environ[key]` (priority 1) picks them up.

### Credential key map

| Resolver key | PipelineConfig field | opencode.json provider mapping |
|---|---|---|
| `GEMINI_API_KEY` | `gemini_api_key` | `provider.google.options.apiKey` |
| `ANTHROPIC_API_KEY` | `anthropic_api_key` | `provider.anthropic.options.apiKey` |
| `MATHPIX_APP_ID` | `mathpix_app_id` | `provider.mathpix.options.appId` |
| `MATHPIX_APP_KEY` | `mathpix_app_key` | `provider.mathpix.options.appKey` |
| `GOOGLE_CLOUD_PROJECT` | `google_cloud_project` | — |
| `GOOGLE_API_KEY` | `google_api_key` | — |
| `XAI_API_KEY` | `xai_api_key` | — |

### config.example.yaml changes

- Add `google_api_key` and `xai_api_key` to the API Keys section
- Remove `google_application_credentials` comment (dead field)
- Add a `credentials:` section that mirrors what `resolve_credential()` reads from config.yaml, for clarity
- Keep the existing flat top-level keys for backward compatibility; the resolver reads the `credentials` section primarily, but falls back to flat top-level keys if no `credentials` section exists

Actually, simpler: keep flat keys in config.example.yaml since that's what PipelineConfig._from_dict already reads. Add the two missing ones. Remove the dead one.

## Files to Change, Ranked by Effort/Risk

| # | File | Change | Effort | Risk | Notes |
|---|---|---|---|---|---|
| 1 | `src/ocr_pipeline/credentials.py` | **CREATE** — new module | Medium | Low | The central artifact. Write once, test thoroughly. |
| 2 | `src/ocr_pipeline/engines/base.py` | **DELETE** CredentialStore class (lines 203-315) | Low | Low | No other code depends on storing creds in base.py. Mathpix and merger import it explicitly — those change separately. |
| 3 | `src/ocr_pipeline/engines/__init__.py` | Remove CredentialStore from imports/exports; replace 3 `os.environ.get()` calls | Low | Low | Just swap function calls. |
| 4 | `src/ocr_pipeline/engines/google_doc_ai.py` | Replace `os.environ.get("GOOGLE_API_KEY")` (line 46) with `resolve_credential("GOOGLE_API_KEY")` | Low | Low | One-line change. |
| 5 | `src/ocr_pipeline/engines/mathpix.py` | Replace `CredentialStore()` usage (lines 7, 30-32) with `resolve_credential()` | Low | Low | MathpixEngine already accepts explicit params — those still take priority, resolver is the fallback. |
| 6 | `src/ocr_pipeline/engines/metadata_vlm.py` | Replace `os.environ.get("GEMINI_API_KEY")` (line 110) with `resolve_credential("GEMINI_API_KEY")` | Low | Low | One-line change. |
| 7 | `src/ocr_pipeline/merger.py` | Replace 3 credential resolution blocks with `resolve_credential()` | Medium | Medium | Three functions change: `_call_gemini` (lines 287-302), `_call_anthropic` (lines 175-190), `_call_grok` (lines 377-381). Each drops 10+ lines of inline resolution logic. |
| 8 | `src/ocr_pipeline/config.py` | Add `google_api_key`, `xai_api_key` fields; remove `google_application_credentials`; update `_ENV_MAP`, `_from_dict`, `apply_env_credentials` | Medium | Medium | Touches the dataclass, loader, and env map. Must keep backward compat for existing fields. |
| 9 | `src/ocr_pipeline/mcp_server.py` | Remove `apply_env_credentials()` calls (lines 136, 343, 545); the function can be deprecated or removed from config.py | Low | Low | Credential resolution moves to the consumers, not the config init. |
| 10 | `config.example.yaml` | Add `google_api_key`, `xai_api_key`; remove `google_application_credentials` comment | Low | Low | Documentation-only change. |

## Migration Strategy

**Phase 1 (low risk):** Create `credentials.py` with the resolver. All existing code continues to work unchanged. Write tests for the new module.

**Phase 2 (consumer swap):** One consumer at a time, replace its credential resolution with `resolve_credential()`. Start with the simplest ones (google_doc_ai.py, metadata_vlm.py), then merger.py, then mathpix.py, then create_engine. Each change is independently testable.

**Phase 3 (cleanup):** Delete `CredentialStore` from base.py. Remove `apply_env_credentials()` from config.py. Remove dead fields from PipelineConfig. Update config.example.yaml.

**Phase 4 (documentation):** Update README with the new credential resolution rules, MCP configuration instructions, and the environment variable reference.

## Risks & Mitigations

1. **opencode.json provider→key mapping could change**: If opencode changes its JSON schema, the resolver needs updating. Mitigation: the `provider.*.options` mapping is documented in a single dictionary in `credentials.py`, with a comment referencing the opencode schema version.

2. **Circular import**: `credentials.py` imports from `config.py` (for `config.yaml` path), and consumers import from `credentials.py`. Mitigation: `resolve_credential` takes `config=None` — it reads config.yaml from a hardcoded path relative to the project root, not from a `PipelineConfig` instance. No circular dependency.

3. **Performance**: `resolve_credential()` reads config.yaml and opencode.json on every call. Mitigation: module-level `_cache` dict with TTL or simply accept the cost (these files are tiny, and credential resolution happens once per engine init / once per merge call, not per-page).

4. **MCP env vars not set**: If the user doesn't configure `mcp.ocr-pipeline.environment` in opencode.json, the MCP process has no API keys in its environment. The resolver falls through to config.yaml and opencode.json `credentials` section. Mitigation: clear documentation in the README showing exactly how to configure MCP credentials both ways.

5. **config.yaml path ambiguity**: The resolver needs to know WHERE config.yaml is. For CLI, it's relative to CWD. For MCP, it's relative to the project root. Mitigation: the resolver checks multiple paths (CWD/config.yaml, project_root/config.yaml) — same as `_load_config` already does.

## Subdelegation Log

No mules spawned — this was a pure analysis and architecture task that required reading all source files to build a complete picture before making recommendations.
