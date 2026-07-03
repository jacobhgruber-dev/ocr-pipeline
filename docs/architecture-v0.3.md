# OCR Pipeline — Architecture Review & Forward Design (v0.3)

**Status:** review draft · **Scope:** 30 input formats / 82 extensions / ~29 source
classes / ~393 tests · **Author:** architecture review · **Date:** 2026-07-03

This document (1) describes the architecture as it actually runs today, (2) names the
architectural debt honestly, (3) recommends a forward design, and (4) prioritizes changes
into *blocking for v0.3* vs *nice-to-have for v0.4*. It answers the ten review questions
inline (tagged **[Q1]**…**[Q10]**).

A guiding bias throughout: **this is a Python library, not a spacecraft.** Some
inconsistency is acceptable. Several recommendations below are explicitly *"don't do this
yet."* The goal is a coherent, shippable v0.3 — not a perfect one.

---

## 1. Current Architecture

### 1.1 Data flow

```
run()                                     # glob input_extensions in input_dir
 └─ process_one(path)                      # per file, ThreadPoolExecutor(pdf_concurrency)
     ├─ detect_source(path) -> DocumentSource
     ├─ FileIdentity + sha256 + checkpoint load
     └─ ThreadPoolExecutor(max_workers)    # per page of THIS file
         └─ PageProcessor.process(ctx)      # one PageContext per page
             ├─ 1. extract_text  (source.extract_text)   → EXTRACTED (fast path)
             ├─ 2. render_page   (source.render_page)     → PNG
             ├─ 3. run_ocr       (engine_runner)          → parallel engines + circuit breakers
             ├─ 4. merge         (skip / single / VLM ensemble)
             ├─ 5. cost + confidence
             └─ 6. save          (per-page formatters + raw JSON)
     └─ _produce_document_output(...)       # ⚠ PDF ONLY: metadata + concatenated .md
 └─ _produce_collection_output()            # ⚠ globs */document.md (PDF only)
```

### 1.2 Key abstractions (all present and basically sound)

| Layer | Contract | Location | Assessment |
|---|---|---|---|
| **DocumentSource** ABC | `source_format`, `source_mimetype`, `page_count`, `render_page`, `extract_text` | `sources/base.py` | Right abstraction; contract under-specified (see §2) |
| **Source registry** | `_EXTENSION_MAP` dict + `detect_source()` + `filetype` magic-byte fallback | `sources/__init__.py` | Works; eager-imports all 28 modules |
| **PageProcessor** | 6-phase `process(PageContext)` with injected `engine_runner`, `vlm_merger`, `postprocessor` | `page_processor.py` | Good DI; leaks PDF/`fitz` specifics |
| **Engines** | `create_engine()` factory + `CircuitBreaker` per engine | `engines/` | Clean; not in scope here |
| **Formatters** | `_FORMATTERS` dict + `get_formatter()`; page-level and doc-level shapes | `formatter.py` | Already a mini-registry |
| **MetadataResult** | flat ~35-field dataclass + `SourceInfo`/`RightsInfo` | `models.py` | Flat but functional |
| **Config** | one flat `PipelineConfig` dataclass (~50 fields) + YAML/env loaders | `config.py` | Flat; some tool paths configurable, others hardcoded |

The v0.2 → v0.3 multi-format work (`docs/multi-format-architecture.md`) landed the
`DocumentSource` abstraction cleanly. Page-level processing **is** format-agnostic. The debt
is concentrated at the two ends the multi-format work didn't reach: **source-contract
uniformity** (below the abstraction) and **document assembly + metadata** (above it).

---

## 2. Architectural Debt (the honest list)

Ranked by severity. The top three are *correctness* problems — advertised behavior that
does not run — not merely aesthetic.

| # | Severity | Debt | Evidence |
|---|---|---|---|
| D1 | 🔴 **Blocker** | **Document assembly is PDF-only.** `_produce_document_output` is gated `if file_type == "pdf"` (`pipeline.py:393`). All 28 non-PDF formats produce per-page `*_final.md` but **no** `document.md`, YAML frontmatter, document metadata, or `collection.md` entry. | `pipeline.py:392-397`, `574-615` |
| D2 | 🔴 **Blocker** | **Metadata chain half-wired + dead branches.** The real chain is `native → VLM → GROBID → empty`. `sidecar.merge_sidecar_metadata` and `identifier.enrich_metadata` (DOI/ISBN resolution) are fully implemented **and tested** but **never called** in the live path. Worse, the non-PDF native branch inside `_extract_metadata` (`pipeline.py:493`) is unreachable because its only caller is the PDF-gated D1. | mule audit: 0 call sites in `src/` outside their own modules |
| D3 | 🔴 **Blocker** | **`extract_metadata()` is not on the ABC.** 7 sources (`pdf, docx, excel, pptx, csv, image, txt`) don't define it, yet `pipeline.py:495` calls `source.extract_metadata()` polymorphically → `AttributeError` (currently swallowed by a bare `except`, silently dropping metadata for those formats). | `sources/base.py` (no method), `pipeline.py:495` |
| D4 | 🟠 High | **`page_count` error contract diverges 5 ways.** `PdfSource` returns `0` with the comment `# Consistent with other sources: 0 = failed/corrupt` (`pdf.py:37`) — which is **false**: 21 sources return `1`, `djvu`/`image` fall back to `1`, `epub`/`excel`/`pptx` return bare `len()` (→ `0` when empty), and `docx`/`epub`/`excel`/`pptx` can *raise*. The pre-flight page count in `run()` (`pipeline.py:186-193`) silently mis-estimates. | mule audit Table A |
| D5 | 🟠 High | **`ExcelSource` TOCTOU thread-safety bug.** `_load_sheets` sets `self._sheet_names` before populating `self._sheets_data`; the guard at `excel.py:42` checks both non-`None`, but `_sheets_data` is set to `{}` first, so a second page-thread can pass the guard and read an empty/partial dict → `KeyError`/data loss. Pipeline shares one source across the page thread pool. | `excel.py:40-62`, `pipeline.py:350-361` |
| D6 | 🟡 Med | **`extract_text` / `render_page` signaling inconsistent.** OOR page → some raise `RenderError`, some return `("", None)`; `("", None)` is overloaded (means both "no text, go OCR" *and* "empty/error"); `ExcelSource` returns non-empty text with a `None` path (`excel.py:85`); `render_page` has 4 variants (real raster / PyMuPDF / `ddjvu` CLI / bare `NotImplementedError`), and `DjvuSource` mixes `NotImplementedError` + `RenderError` in one method. | mule audit "Inconsistencies" |
| D7 | 🟡 Med | **Eager imports.** `ocr_pipeline/__init__.py:13` imports `Pipeline` → `extractor`/`renderer` → `import fitz` at module top; `sources/__init__.py` eager-imports all 28 modules; `image.py` eager-imports `pillow_heif`. `import ocr_pipeline.sources` costs ~fitz(77ms)+numpy(51ms)+pillow_heif(30ms)+lxml(30ms). Wall ~160ms. | mule perf report |
| D8 | 🟡 Med | **9 formats have zero tests** (`ebook, marc, gis, dxf, media, tei, svg, pages, fb2`); all source tests live in one 85-test file; no contract-conformance harness. | mule test survey |
| D9 | 🟢 Low | **Missing-tool degradation disguised as success.** `djvu`/`ebook`/`media` bake `"install X"` strings into returned page text as clean `(text, path)` — indistinguishable from real content. | mule audit |
| D10 | 🟢 Low | **Stale/aspirational docs.** `STATUS.md` lists 18 formats (now ~30); `comprehensive-metadata-architecture.md` proposes an 80-field nested `MetadataResult` that does **not** match `models.py`. Discoverability is manual and drifts. | `STATUS.md:44`, doc vs `models.py` |

**Theme:** the abstraction is good; the *contract underneath it* and the *assembly above it*
were never finished. Most fixes are cheap because the hard part (the ABC, the registry, the
formatter registry, the sidecar/identifier code) already exists.

---

## 3. Findings & Recommendations by Question

### Q1 — Source Registry Pattern
**Keep the explicit table; make it lazy. Do *not* adopt decorators/auto-discovery/entry-points.**

The `_EXTENSION_MAP` dict is *not* the problem — 82 entries in one greppable, diffable,
deterministic table is a feature, not a smell. The problem is that populating it
**eager-imports all 28 modules** (D7). Fix the import cost, keep the explicitness:

- Map extension → a lightweight import target (dotted path string or tiny lambda), and import
  the module **only when a matching file is detected**:
  ```python
  _REGISTRY: dict[str, str] = {".pdf": "ocr_pipeline.sources.pdf:PdfSource", ...}
  def detect_source(path):
      target = _REGISTRY.get(path.suffix.lower()) or _sniff(path)
      module, cls = target.split(":")
      return getattr(import_module(module), cls)(path)
  ```
- **Explicit > auto-discovery.** Decorator self-registration *requires importing every module
  to register it* — reintroducing D7 unless you also hand-maintain a manifest (so you've kept
  the table anyway, minus the greppability). Auto-discovery makes conflicts implicit.
- **Extension conflicts** (`.xml` → TEI vs JATS vs generic; `.json` → JSON-LD vs GeoJSON):
  keep extension as the fast path; add a **small** `_AMBIGUOUS: dict[str, Callable]` of
  content-sniff disambiguators for the handful of genuinely overloaded extensions. Do **not**
  build a general content-detection framework.
- **Entry-points / third-party plugins:** over-engineering while all 29 sources live in-repo.
  Revisit only if out-of-tree sources become a real requirement (v0.5+).

*Tradeoff:* lazy dotted-path strings lose import-time type checking of the registry. Acceptable
— the conformance harness (Q7) catches a broken target immediately.

### Q2 — Pipeline Phase Model Coherence
**The phase model is still coherent. Formalize it with source *capability flags* — do not explode into a strategy-class-per-format.**

There are only **three** processing archetypes, not 30:
1. **Text-native** (docx, txt, epub, html, csv, …): `extract_text` always succeeds → never render, never OCR (~22 sources).
2. **Image/scan** (image, comic): render → OCR → merge.
3. **Hybrid** (pdf, djvu): per-page probe — extract if text, else render+OCR.

The current per-page probe (`_try_text_extraction` returns `True` → done) already collapses
these into one flow. A 30-class strategy hierarchy would add ceremony and *more* tests for
*less* clarity. The real debt is that `PageProcessor` **leaks PDF specifics**: `_save_extracted_outputs`
opens the file with `import fitz` to read page dimensions (`page_processor.py:276-283`) — dead
weight and wrong for every non-PDF, and the `_vlm_merge_extracted` re-render path is PDF-shaped.

**Recommendation:** keep the single unified pipeline; drive the render/OCR decision from
declared capabilities (`source.can_render`, `source.can_extract_text` — see Q8) instead of
try/except on `NotImplementedError`; move page-dimension capture behind the source (a source
that can't render returns no dimensions). Net: fewer branches, no new class hierarchy.

### Q3 — Metadata Extraction Chain
**Wire in the orphaned code, run it for *all* formats, and resolve identifiers opportunistically (not at one fixed stage).** This is the highest-value cheap win — the code exists and is tested.

Recommended default order (each step fills only still-empty fields):

1. **format-native** `extract_metadata()` — deterministic, free.
2. **sidecar** merge — human-curated. *Supplement by default* (fill-empty), with an opt-in
   `authoritative: true` key in the `.meta.yaml` to force override for curated collections.
   (Answers "override or supplement?" → supplement, with an escape hatch.)
3. **early identifier resolution** — *if a DOI/ISBN is already known*, resolve via
   CrossRef/OpenLibrary now. This is authoritative bibliographic data and can **short-circuit
   the expensive VLM call entirely.** (Answers "should identifier resolution happen earlier?"
   → yes, *when an identifier is already in hand*.)
4. **VLM** — fuzzy fallback, only for still-missing fields.
5. **GROBID** — PDF academic, only for still-missing fields.
6. **late identifier resolution** — resolve any DOI/ISBN newly surfaced by VLM/GROBID.

**Precedence policy** (document it, don't build a rules engine): authoritative sources
(sidecar-authoritative, CrossRef/OpenLibrary) > deterministic native > fuzzy VLM. Default merge
is fill-empty in chain order. Expose a simple `metadata_sources: [...]` list in config to
reorder/disable stages; that's sufficient configurability without a precedence DSL.

Blocking because it's a correctness gap (advertised sidecar + DOI/ISBN features silently don't
run) and depends on D1/D3 being fixed first.

### Q4 — Config Surface
**Don't build a `SourceConfig` class hierarchy. Do add (a) a flat `tool_paths` map and (b) a `required_tools` class attribute per source.**

A nested per-source config graph (loading, merging, env-mapping, validation) is real ceremony
for a system where **most sources need zero config**. The flat `PipelineConfig` is ugly but
works. The *actual* inconsistency worth fixing: external tools are configured ad hoc —
`marker_venv`, `surya2_venv`, `grobid_url`, `google_processor_id` are in config, but
**calibre (`ebook-convert`), ffmpeg (`ffprobe`), `ddjvu`/`djvutxt`, and `unrar` are assumed on
`PATH`** with no configuration home.

- Add one `tool_paths: dict[str, str]` (tool name → binary/venv path). Sources resolve via a
  shared `resolve_tool("ebook-convert")` (config override → `PATH`). Migrate the existing
  venv/url fields into it over time.
- Let each source declare `REQUIRED_TOOLS: tuple[str, ...]` (also feeds Q8 discoverability and
  Q7 test skips). This is *declaration*, not a config object.

Additive, low-risk, no hierarchy. Defer anything larger.

### Q5 — Error Contract Consistency
**Standardize the ABC contract. This is the highest-leverage cheap fix and is partly blocking (D3, D4).** Accept that some cosmetic divergence will remain.

Define in `base.py` and enforce via the Q7 harness:

| Method | Standard contract |
|---|---|
| `page_count` | Returns `int ≥ 1` for a readable doc; **raises `SourceError`** on corrupt/unreadable. Kill the `0`-sentinel (and PdfSource's false comment). Provide a `_at_least_one(len)` helper. |
| `extract_text` | Returns `(text, path\|None)`; `("", None)` means **only** "no extractable text → fall through to OCR"; **raises `SourceError`** on hard failure; OOR page index raises (programmer error). No non-empty-text-with-`None`-path. |
| `render_page` | Returns a real PNG `Path`, or **raises `RenderNotSupported`** (a distinct catchable subclass) — never bare `NotImplementedError`. Better: pipeline checks `source.can_render` and never calls it when unsupported. |
| `extract_metadata` | **Added to ABC** with a default returning `MetadataResult(extraction_method="none")` → eliminates D3 across all sources at once. |
| missing tool | Raise `ToolUnavailable` (or set a structured error field); never bake "install X" into returned content (D9). |

Add `SourceError`, `RenderNotSupported`, `ToolUnavailable` under the existing `errors.py`
hierarchy (`OcrPipelineError`). Most of this is base-class defaults + small per-source edits.

### Q6 — Performance
- **Import cost (D7):** the Q1 lazy registry defers all 28 source imports. Additionally make
  `pillow_heif` lazy in `image.py`. `fitz` in `extractor`/`renderer` is a legitimate core dep,
  but `import ocr_pipeline.sources` should not transitively pull it — decouple by not importing
  `Pipeline` in the package `__init__` eagerly, or lazy-import `fitz`. Target: importing the
  registry pulls in *no* heavy libs.
- **Thread safety:** `PdfSource` is stateless (reopens per call) → safe. Most sources cache
  idempotently → benign double-work. **`ExcelSource` is a genuine data-corruption bug (D5)** —
  fix now: build locally and assign the cache in one atomic step (or guard with a `Lock`).
  Then **document the contract**: *source instances must tolerate concurrent read calls.*
  Longer term, note that intra-document page parallelism mainly benefits PDF (which is
  stateless anyway); most non-PDF sources are 1 "page," so per-*file* parallelism is the real
  win and per-*page* threading over a shared stateful source is low-value risk.
- **Memory / >1GB files:** everything is in-memory; `ExcelSource` (`to_python()`) and
  `Fb2Source` (`read_text()`+`fromstring`) materialize whole files. **Not blocking** (rare).
  For v0.4 add a `max_file_bytes` guard (skip-with-warning) and stream the two worst offenders.
  Do **not** build a general streaming framework.

### Q7 — Testing Coverage Gaps
**Adopt a parametrized source-contract conformance harness; keep bespoke tests for format-specific richness on top.** This is the correct strategy for 30 formats.

One parametrized suite that every registered source must pass against a tiny per-format fixture:
`detect_source` returns the right class · `page_count ≥ 1` or raises `SourceError` ·
`extract_text` returns the right tuple shape · `render_page` returns a real PNG or raises
`RenderNotSupported` · `extract_metadata` returns a `MetadataResult`. This closes the 9
zero-coverage formats (D8) at near-zero marginal cost **and** mechanically enforces the Q5
contract. Layer targeted tests (e.g., HTML JSON-LD parsing, EPUB spine order) where behavior is
rich. Land the harness *with* the Q5 standardization — they reinforce each other.

### Q8 — Documentation & Discoverability
**Make each source declare capabilities as class attributes; generate all format docs/CLI/MCP listings from the registry.** Single source of truth that can't go stale (fixes D10).

```python
class DocumentSource(ABC):
    EXTENSIONS: tuple[str, ...] = ()
    source_format: str
    can_extract_text: bool = True
    can_render: bool = False
    provides_metadata: bool = True
    REQUIRED_TOOLS: tuple[str, ...] = ()
```

This one change unifies five concerns: registry (Q1), render decision (Q2), tool config (Q4),
contract/tests (Q5/Q7), and discoverability. Add `ocr-pipeline --list-formats` and generate the
`STATUS.md` table + MCP capability list from `_REGISTRY`. The extension map alone is *not*
sufficient — users need the capability matrix, and hand-maintained tables already drift.

### Q9 — Forward Compatibility
Design the *seams*; don't build the features speculatively.

| Future need | Recommendation | When |
|---|---|---|
| **Large/streaming files** | `max_file_bytes` guard now; targeted streaming for Excel/FB2 | v0.4 |
| **Remote sources (S3/HTTP)** | Keep the ABC local-`Path`-based; add a *fetch-to-temp* front-end for URIs. Don't abstract to byte-streams yet. | v0.4 |
| **Conversion cascades (EPUB→PDF→OCR on text-extract failure)** | Model as an opt-in `source.fallback() -> DocumentSource\|None` (e.g., `EbookSource`→calibre→`PdfSource`); `SourceInfo.converted_from` already exists to record it. Not a general conversion graph. | v0.4 |
| **Multi-file documents (book = chapter files)** | A "collection source" grouping files into one logical doc. `ArchiveSource` partly covers bundles today. | v0.4+ |
| **Version-aware detection (PDF/A, EPUB2/3, TEI vs JATS)** | The Q1 `_AMBIGUOUS` sniff hook is the extension point; full version-awareness is niche. | on demand |

### Q10 — Output Format Strategy
**Formalize the formatter registry to mirror the source registry, split page-level vs document-level formatters, and add formats on demand.** They're already a small registry (`_FORMATTERS`), so all additions are additive.

- **Split the protocol** (it's implicit today): `PageFormatter.format(PageResult)` (markdown,
  json, alto, **hOCR**) vs `DocumentFormatter.format(metadata, pages)` (yaml-frontmatter,
  **TEI**, **METS**). This removes the current ad-hoc two-shape confusion in `formatter.py`.
- **hOCR** — cheap, page-level, complements ALTO (blocks already exist). *v0.3 nice-to-have.*
- **TEI-as-output** — high value for the scholarly use case; GROBID already emits TEI. *v0.4.*
- **METS wrapper** — packages per-page ALTO/hOCR for digital-library/archival workflows; only
  if targeting METS-ALTO consumers. *v0.4, on demand.*

Don't build all four speculatively — the registry makes them pluggable, so add when a consumer
needs one.

---

## 4. Forward Design Sketch (what actually changes)

Concrete, minimal shape after v0.3. New/changed pieces only:

```
sources/base.py        + capability attrs (EXTENSIONS, can_render, …, REQUIRED_TOOLS)
                       + extract_metadata() default → MetadataResult("none")
                       + standardized page_count/extract_text/render_page contract
sources/__init__.py    _REGISTRY: dict[str,str] (dotted paths, lazy import)
                       + _AMBIGUOUS disambiguators for .xml/.json
errors.py              + SourceError, RenderNotSupported, ToolUnavailable
sources/excel.py       atomic cache assignment (fix TOCTOU)
sources/image.py       lazy pillow_heif
sources/_tools.py      resolve_tool(name)  ← config tool_paths → PATH
config.py              + tool_paths: dict[str,str]; + metadata_sources: list[str]
pipeline.py            _produce_document_output: run for ALL formats (drop PDF gate)
                       _extract_metadata: native → sidecar → id-resolve → VLM → GROBID → id-resolve
metadata.py (new)      thin orchestrator wrapping sidecar.merge + identifier.enrich (wire the orphans)
page_processor.py      capability-driven render/OCR; remove fitz-specific dimension code
formatter.py           PageFormatter / DocumentFormatter split; registry mirrors sources
tests/test_source_contract.py (new)  parametrized conformance across all registered sources
```

Nothing here is a rewrite. The `DocumentSource` ABC, the registry, the formatter registry, and
the sidecar/identifier modules all already exist — v0.3 mostly **finishes wiring what's there**
and **tightens the contract**.

---

## 5. Prioritization

### 🔴 v0.3 — Blocking (correctness & multi-format coherence)
These are advertised-but-not-working behaviors and a data-corruption bug.

1. **D1** — Un-gate document assembly from PDF-only; run `_produce_document_output` /
   `collection.md` for all formats. *(Q2)*
2. **D2/D3** — Wire the metadata chain for all formats; add `extract_metadata` to the ABC with a
   safe default; wire in the orphaned **sidecar** + **identifier (DOI/ISBN)** resolution in the
   Q3 order. *(Q3, Q5)*
3. **D4** — Standardize `page_count` (≥1 or raise `SourceError`); delete the false PdfSource
   sentinel/comment; fix the pre-flight count. *(Q5)*
4. **D5** — Fix `ExcelSource` TOCTOU (atomic cache assignment). *(Q6)*
5. **Capability attributes** on `DocumentSource` (`EXTENSIONS`, `can_render`,
   `can_extract_text`, `provides_metadata`, `REQUIRED_TOOLS`). Foundation for Q1/Q4/Q7/Q8. *(Q8)*

### 🟠 v0.3 — Should (cheap, high-leverage, enables the above)
6. **Lazy source registry** (dotted-path targets) — fixes import cost + extensibility. *(Q1/Q6)*
7. **Source-contract conformance harness** — closes the 9 zero-coverage formats, enforces Q5. *(Q7)*
8. **Normalize `extract_text`/`render_page` signaling** (`RenderNotSupported`; capability-gated
   render; stop `("",None)` overloading). *(Q5)*

### 🟡 v0.4 — Nice-to-have
- Formatter `Page`/`Document` split + **hOCR**, then **TEI-out** / **METS** on demand. *(Q10)*
- `metadata_sources` precedence config + two-phase identifier resolution polish. *(Q3)*
- `tool_paths` consolidation for calibre/ffmpeg/ddjvu/unrar. *(Q4)*
- `max_file_bytes` guard + streaming for Excel/FB2. *(Q6)*
- Remote (fetch-to-temp) sources; conversion cascades via `source.fallback()`; multi-file
  collection sources. *(Q9)*
- `--list-formats` CLI + generated `STATUS.md`/MCP listing from the registry. *(Q8/D10)*

### ⛔ Explicitly NOT now (avoid over-engineering)
- Full per-source `SourceConfig` class hierarchy. *(Q4)*
- Strategy-class-per-format (30 classes). *(Q2)*
- Entry-points / third-party plugin system. *(Q1)*
- General streaming framework or general conversion graph. *(Q9/Q6)*
- The 80-field nested `MetadataResult` from `comprehensive-metadata-architecture.md`. The flat
  model works; nest incrementally *only* where a consumer demands it. *(Q3/D10)*

---

## Appendix — Evidence base

Findings were cross-checked against the code by targeted sub-audits:
- **Error-contract & capability matrix** across all 29 source classes (page_count / extract_text
  / render_page conventions, `extract_metadata` presence, external tools, lazy imports).
- **Test-coverage & metadata-wiring survey** (per-format test counts; grep-verified that
  `merge_sidecar_metadata` and `enrich_metadata` have **zero** call sites in `src/` outside their
  own modules; `adapters/paper_source.py` is an unimplemented MCP stub).
- **Import-cost & thread-safety measurement** (importtime breakdown; `ExcelSource` TOCTOU;
  large-file materialization in Excel/FB2).

Key file:line anchors: `pipeline.py:393` (PDF-only assembly), `pipeline.py:488-537`
(metadata chain), `pdf.py:36-37` (false page_count sentinel), `excel.py:40-62` (TOCTOU),
`sources/__init__.py:36-64` (eager imports), `__init__.py:13` (eager `Pipeline`/`fitz`),
`page_processor.py:276-283` (PDF-specific leak in a generic path).
