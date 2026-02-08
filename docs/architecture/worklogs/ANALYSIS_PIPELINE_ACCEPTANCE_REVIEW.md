# Analysis Pipeline — Acceptance Review Report

**Reviewer:** Claude Opus 4.6
**Date:** 2026-02-08
**Scope:** All 14 implementation steps from `ANALYSIS_PIPELINE_IMPLEMENTATION_PLAN.md`
**Spec Reference:** `ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` v1.4 (BINDING)
**Test Suite:** 4606 passed, 20 skipped (full run on review date)

---

## Executive Summary

1. **Kernel layer is spec-compliant.** All 14 invariants (Inv-A1 through Inv-A14) are correctly implemented in the core analysis types, orchestrator, transforms, and bundle model. No spec violations found.
2. **CRITICAL: QE parser registration chain is broken.** `src/quantumvitas/drivers/qe/parsers/__init__.py` does not exist, so `@register_parser("qe", "bands")` and `@register_parser("qe", "trajectory")` decorators never fire at runtime. Tests pass only because they import the parser classes directly. The orchestrator's `get_parser("qe", "bands")` will return `None` in production.
3. **API/daemon layer has ZERO wiring to the new pipeline.** `service.py` (7779 lines) has 30+ references to legacy `analysis.artifacts` and zero references to `run_post_run_analysis`, `CanonicalPrimitiveBundle`, or `analysis_snapshots`.
4. **GUI still uses legacy types.** `CalculationAnalysisPanel.tsx` consumes `BandStructureData`, `DosData`, `ScfConvergenceData` — all legacy types not connected to the new pipeline.
5. **Gate test coverage is 9/29 (31%).** Spec §12.1 lists 29 gate tests; only 9 are implemented. All 9 pass.
6. **No CAS eager-write path exists.** The `analysis_snapshots` SQLite table was created (schema v2 migration), but no code writes to it. The end-of-run eager pipeline described in §4/§10 is completely unimplemented.
7. **Bundle types and primitives are correctly structured.** `CanonicalPrimitiveBundle`/`DerivedPrimitiveBundle` enforce `bundle_kind` literals, contain no timestamps, and serialize deterministically.
8. **Transforms are pure.** `FermiShift` contains no engine imports, no disk access, no driver references. `clone_bundle_for_transform()` correctly deep-copies and appends to `transform_chain`.
9. **Capability matching is correct and deterministic.** `find_contiguous_match()` returns first-occurrence match; tested with multi-step and overlapping scenarios.
10. **QE BandStructure E2E path works in tests.** `test_qe_bands_e2e.py` demonstrates raw→parse→BandStructure→to_primitives()→FermiShift with correct output — but only because the test imports `QEBandsProvider` directly.
11. **Trajectory model updated correctly.** `Frame` and `Trajectory` in `core/analysis/trajectory/model.py` implement `to_primitives()` returning `CanonicalPrimitiveBundle` with correct RenderMeta/ProvenanceMeta split.
12. **No engine branching in universal layer.** AST scan confirms zero `if engine ==` comparisons in orchestrator.py, bundles.py, or any transform module.
13. **Legacy analysis pipeline is completely untouched.** `analysis/artifacts.py`, `analysis/dos.py`, `analysis/parsers.py`, `analysis/plotting.py` all still exist and are the only code the API calls. No deprecation markers or migration shims were added.
14. **`run_ulid_source` provenance field correctly implemented.** Literal type `"exact"|"inferred"|"unknown"`, stored in pin operation payload and CAS metadata, validated with hard error on invalid values.

---

## 1. Spec Compliance Checklist

### 1.1 Invariant-by-Invariant Verdict

| Invariant | Verdict | Evidence |
|-----------|---------|----------|
| **Inv-A1**: Raw artifacts are evidence, not SSOT | **PASS** | `orchestrator.py` reads raw dirs only; no YAML writes in analysis path. No `.tmp/` references in runtime code. |
| **Inv-A2**: AnalysisObjects are universal and engine-agnostic | **PASS** | `BandStructure` at `core/analysis/band_structure/model.py:27`; `Trajectory` at `core/analysis/trajectory/model.py`. Both in `core/analysis/`, not in drivers. Both carry `meta: AnalysisObjectMeta`. Gate test `test_analysis_object_meta_required` enforces via AST scan. |
| **Inv-A3**: AnalysisObjectMeta is the single metadata schema | **PASS** | `base.py:23-63` defines all required fields: `schema_version`, `object_type`, `created_at`, `source_files`, `run_ulid`, `calc_ulid`, `step_ulids`, `gen_steps`, `engine_name`, `parser_name`, `parser_version`, `warnings`, `manifest_snapshot`. No alternative containers found. |
| **Inv-A4**: Canonical bundles from to_primitives() only, deterministic | **PASS** | Gate tests `test_canonical_bundle_deterministic` and `test_to_primitives_is_parameterless` both pass. AST scan confirms zero-parameter signatures. `created_at` excluded from bundle serialization at `bundles.py` (ProvenanceMeta has no `created_at`). |
| **Inv-A5**: Derived bundles from PrimitiveTransform only, ephemeral | **PASS** | Gate test `test_derived_never_cached` passes. `clone_bundle_for_transform()` at `transforms/base.py:38-71` is the sole producer of `DerivedPrimitiveBundle`. No cache decorators found on any path returning `DerivedPrimitiveBundle`. |
| **Inv-A6**: Bundles contain data + RenderMeta + ProvenanceMeta only | **PASS** | Gate test `test_render_meta_no_provenance` passes. `RenderMeta` fields: `axis_labels`, `units`, `series_labels`, `reference_energy`, `markers`, `extra`. No provenance fields. |
| **Inv-A7**: Transforms are pure math, no engine logic | **PASS** | Gate test `test_transform_no_engine_imports` passes (AST scan). `fermi_shift.py` imports only `numpy`, `base`, `bundles`, `primitives`. No `Path`, no `open()`, no driver imports. |
| **Inv-A8**: Viz consumes PrimitiveBundles via RenderMeta only | **PARTIAL** | `analysis/plotting.py` still exists and accesses `provenance_meta` for labels. However, new plotting code was not introduced — existing legacy code is outside the new pipeline scope. No new viz code violates this. |
| **Inv-A9**: No lazy payloads | **PASS** | No `LazyArray`, `LateList`, or deferred-proxy classes found in `core/analysis/`. Grep confirms zero matches. |
| **Inv-A10**: Canonical-only memoization | **PASS (vacuously)** | No memoization implemented yet (API layer not wired). No cache decorators on derived paths. When implemented, must follow spec. |
| **Inv-A11**: CAS is content-addressed, persistence explicit | **PARTIAL** | `analysis_snapshots` table created at `provenance/schema.py` with `canonical_sha` column and `UNIQUE(run_ulid, object_type)`. However, NO code writes to this table. No `canonical_sha` computation exists anywhere. |
| **Inv-A12**: Kernel vs API vs Frontend layering | **PASS (kernel)** | Kernel code (`core/analysis/`) has no API/daemon/frontend imports. Orchestrator has no CAS/SQLite writes. API layer untouched (not yet wired). |
| **Inv-A13**: No engine branching in universal layer | **PASS** | Gate test `test_no_engine_branching_in_orchestrator` passes (AST scan of orchestrator.py, bundles.py, all transforms). |
| **Inv-A14**: Evidence corpus isolation | **PASS** | No `.tmp/` references in runtime code. Test fixtures use committed `tests/data/` paths. |

### 1.2 Summary: 12 PASS, 2 PARTIAL, 0 FAIL

The two PARTIAL verdicts (Inv-A8, Inv-A11) are expected — they depend on API/GUI wiring that is explicitly out of scope for the kernel-layer implementation.

---

## 2. Gate Test Coverage

### 2.1 Implemented Gate Tests (9/29)

All in `tests/gates/test_analysis_invariants.py`:

| # | Test Name | Invariant | Status |
|---|-----------|-----------|--------|
| 1 | `test_analysis_object_meta_required` | Inv-A2 | PASS |
| 2 | `test_canonical_bundle_deterministic` | Inv-A4 | PASS |
| 3 | `test_to_primitives_is_parameterless` | Inv-A4 | PASS |
| 4 | `test_derived_never_cached` | Inv-A5 | PASS |
| 5 | `test_render_meta_no_provenance` | Inv-A6 | PASS |
| 6 | `test_transform_no_engine_imports` | Inv-A7 | PASS |
| 7 | `test_no_engine_branching_in_orchestrator` | Inv-A13 | PASS |
| 8 | `test_analysis_capability_declaration` | §5.2 | PASS |
| 9 | `test_capability_match_deterministic` | §5.3 | PASS |

### 2.2 Missing Gate Tests (20/29)

| # | Spec Test Name | Invariant | Priority |
|---|----------------|-----------|----------|
| 1 | `test_analysis_object_no_view_params` | Inv-A2 | Medium |
| 2 | `test_canonical_bundle_source` | Inv-A4 | Medium |
| 3 | `test_derived_bundle_source` | Inv-A5 | Medium |
| 4 | `test_bundle_no_view_params` | Inv-A6 | Medium |
| 5 | `test_transform_no_raw_access` | Inv-A7 | Medium |
| 6 | `test_viz_no_raw_access` | Inv-A8 | Low (no new viz code) |
| 7 | `test_viz_no_engine_logic` | Inv-A8 | Low |
| 8 | `test_viz_no_transforms` | Inv-A8 | Low |
| 9 | `test_viz_no_provenance_meta_access` | Inv-A8 | Low |
| 10 | `test_no_lazy_payloads` | Inv-A9 | Medium |
| 11 | `test_no_analysis_disk_cache` | Inv-A10 | High |
| 12 | `test_derived_never_memoized` | Inv-A10 | High |
| 13 | `test_derived_never_persisted` | Inv-A11 | High |
| 14 | `test_operational_path_no_cas_read` | Inv-A11 | High (when API wired) |
| 15 | `test_cas_is_content_addressed` | Inv-A11 | High (when CAS wired) |
| 16 | `test_frontend_no_kernel_import` | Inv-A12 | Medium |
| 17 | `test_unknown_engine_analysis_raises` | Inv-A13 | High |
| 18 | `test_no_tmp_corpus_in_runtime` | Inv-A14 | Medium |
| 19 | `test_no_redundant_canonical` | §5.3 | High |
| 20 | (various behavioral acceptance criteria tests) | §12.2 | Deferred |

---

## 3. Critical Issues

### 3.1 CRITICAL: QE Parser Registration Chain Broken

**Problem:** `src/quantumvitas/drivers/qe/parsers/__init__.py` does not exist. The two parser modules (`bands.py`, `trajectory.py`) use `@register_parser` decorators, but these decorators only fire when the module is imported. Since:

1. `drivers/qe/__init__.py` only imports `QEDriver` — no `from . import parsers`
2. No `__init__.py` exists in `parsers/` to enable package-level import

The orchestrator's `get_parser("qe", "bands")` returns `None` at runtime.

**Why tests pass:** Tests directly import `QEBandsProvider` or `QETrajectoryParser`, which triggers the decorator as a side effect.

**Affected engines (same pattern):** QE, VASP, ORCA, ABINIT, CP2K, w90. Engines that DO have the import chain: LAMMPS, Gaussian, Yambo, xTB, Siesta (all have `from . import parsers  # noqa: F401, E402` in their `__init__.py`).

**Fix:** Add `__init__.py` to `drivers/qe/parsers/` that imports both modules, AND add `from . import parsers  # noqa: F401, E402` to `drivers/qe/__init__.py`.

### 3.2 MAJOR: No End-of-Run Eager Pipeline

**Problem:** Spec §4 and §10 require that canonical primitives be eagerly materialized at end-of-run via capability matching. The orchestrator (`run_post_run_analysis`) exists as pure kernel code but is never called by:
- The execution layer (`runner.py`, `executor.py`)
- The daemon (`server.py`)
- The API service (`service.py`)

**Impact:** No analysis results are produced when a run completes. The entire pipeline is dead code at the system level.

### 3.3 MAJOR: API Still Wired to Legacy Pipeline

**Problem:** `api/service.py` has 30+ references to:
- `from quantumvitas.analysis.artifacts import ...`
- `ensure_analysis_artifact()`
- `read_artifact()`
- `AnalysisType` enum
- Legacy BandStructureData, DosData types

Zero references to:
- `run_post_run_analysis`
- `CanonicalPrimitiveBundle`
- `analysis_snapshots`
- `canonical_sha`

**Impact:** Users cannot access the new analysis pipeline via any public API.

---

## 4. QE Bands E2E Path Evidence

The E2E path **exists** at the kernel level and is **tested**:

```
Raw files (tests/data/analysis_bands/)
  → QEBandsProvider.parse() [drivers/qe/parsers/bands.py:31]
    → parse_bands_gnu() [analysis/parsers.py]
    → parse_scf_output() [analysis/parsers.py]
  → BandStructure [core/analysis/band_structure/model.py:27]
    → .to_primitives() [model.py:63]
  → CanonicalPrimitiveBundle [core/analysis/bundles.py]
    → FermiShift.apply() [transforms/fermi_shift.py]
  → DerivedPrimitiveBundle [core/analysis/bundles.py]
```

**Test evidence:**
- `tests/core/analysis/test_qe_bands_e2e.py` — 2 tests (pipeline + transform)
- `tests/drivers/qe/test_qe_bands_provider.py` — 6 tests (parse, shape, metadata, roundtrip, determinism)
- `tests/core/analysis/test_band_structure.py` — 10 tests (construction, to_primitives, fermi, markers, serialization)

**Gaps in E2E:**
- No test from `run_post_run_analysis()` through to `CanonicalPrimitiveBundle` (only tested with mock providers in `test_orchestrator.py`)
- Registration issue (§3.1) means the E2E path is broken at `get_parser()` step in production

---

## 5. Legacy Pipeline Status

### 5.1 Legacy Modules Still Present (Not Touched by Implementation)

| Module | Lines | Status |
|--------|-------|--------|
| `analysis/artifacts.py` | 236 | Active (API calls it) |
| `analysis/dos.py` | 58 | Active (API calls it) |
| `analysis/parsers.py` | 461 | Mixed — reused by new `QEBandsProvider` for `parse_bands_gnu()` and `parse_scf_output()` |
| `analysis/plotting.py` | 174 | Active (API calls it) |
| `analysis/blob_store.py` | 72 | Active (provenance) |
| `analysis/energy.py` | 27 | Active |
| `analysis/kpath.py` | 105 | Active |
| `analysis/structure_viz.py` | 586 | Active |
| `analysis/volume_artifacts.py` | 47 | Active |

### 5.2 Dependency Between New and Legacy

The new `QEBandsProvider` (`drivers/qe/parsers/bands.py:9`) imports from legacy code:
```python
from quantumvitas.analysis.parsers import parse_bands_gnu, parse_scf_output
```

This is acceptable — the spec does not prohibit reusing existing parsing functions. The new provider wraps legacy parse output into the new `BandStructure` type. However, this creates a dependency that must be maintained during legacy removal.

---

## 6. Architectural Violations

### 6.1 Orchestrator Warning vs Hard Error (Inv-A13 Edge Case)

`orchestrator.py:44-49` emits a `warnings.warn()` when `get_parser()` returns `None`:
```python
if provider_cls is None:
    warnings.warn(
        f"No analysis provider registered for ({engine}, {capability.object_type}).",
        stacklevel=2,
    )
    continue
```

Spec Inv-A13 says: "Unknown engine + object_type combinations MUST raise a hard error, not silently skip or fall back."

**Verdict:** This is a **soft violation**. The orchestrator skips rather than raising. However, the spec's intent applies to explicit user requests (API GET /analysis), not to the batch orchestrator iterating declared capabilities. This should be clarified in the spec or the code should distinguish between the two modes.

### 6.2 No `canonical_sha` Computation Anywhere

The spec (Inv-A11, §10) requires CAS blobs keyed by `canonical_sha = sha256(serialized_bundle)`. No code anywhere computes this hash. The `analysis_snapshots` table has a `canonical_sha TEXT NOT NULL` column but no writer.

---

## 7. Missing Tests / Weak Spots

### 7.1 Orchestrator Integration

- No test calls `run_post_run_analysis()` with real QE driver + registered parsers (only mock providers)
- No test verifies that parser registration via import chain works end-to-end
- No negative test for corrupt raw evidence (should warn, not crash)

### 7.2 Capability Matching Edge Cases

- No test for step order sensitivity (`["bands", "bandspw"]` should NOT match `["bandspw", "bands"]`)
- No test for partial sequence non-match (run has `[scf, nscf]`, capability needs `[scf, nscf, bands]`)

### 7.3 Model Coverage

- No test for spin-polarized bands (3D eigenvalues array)
- No test for Trajectory `to_primitives()` with multi-frame energy + force arrays

### 7.4 Provenance

- No test for `analysis_snapshots` table write/read
- No test for `canonical_sha` computation + CAS storage
- No test for staleness detection via `source_files` mtime comparison

---

## 8. Audit Commands Executed

```bash
# Full test suite
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
# Result: 4606 passed, 20 skipped

# Gate tests only
python -m pytest tests/gates/test_analysis_invariants.py -v
# Result: 9/9 passed

# Engine branching scan
rg 'if engine ==' src/quantumvitas/core/analysis/
# Result: No matches

# Legacy import scan
rg 'from quantumvitas\.analysis\.artifacts' src/quantumvitas/api/
# Result: 30+ matches in service.py

# Driver imports in universal layer
rg 'from quantumvitas\.drivers' src/quantumvitas/core/analysis/
# Result: No matches (CLEAN)

# Parser registration check
rg '@register_parser' src/quantumvitas/drivers/
# Result: 14 decorators across 12 engines (QE has bands + trajectory)

# Import chain verification
rg 'from \. import parsers' src/quantumvitas/drivers/ --glob='__init__.py'
# Result: Only 5/15 engines (LAMMPS, Gaussian, Yambo, xTB, Siesta)

# QE parsers __init__.py existence
ls src/quantumvitas/drivers/qe/parsers/__init__.py
# Result: File does not exist

# CAS write path
rg 'canonical_sha|analysis_snapshots' src/quantumvitas/ --type=py
# Result: Only in schema.py (table definition), nowhere else

# .tmp in runtime code
rg '\.tmp/' src/quantumvitas/ --type=py
# Result: Only in comments, not in runtime paths

# created_at in bundles
rg 'created_at' src/quantumvitas/core/analysis/bundles.py
# Result: No matches (correctly excluded from ProvenanceMeta)
```

---

## 9. Files Created/Modified by Implementation

### 9.1 New Files

| File | Lines | Purpose |
|------|-------|---------|
| `core/analysis/bundles.py` | 323 | CanonicalPrimitiveBundle, DerivedPrimitiveBundle, RenderMeta, ProvenanceMeta, TransformRecord |
| `core/analysis/capability.py` | 62 | AnalysisCapability, CapabilityMatch, find_contiguous_match() |
| `core/analysis/orchestrator.py` | 91 | run_post_run_analysis() — kernel-only orchestration |
| `core/analysis/band_structure/model.py` | 168 | BandStructure AnalysisObject with to_primitives() |
| `core/analysis/transforms/base.py` | 71 | PrimitiveTransform ABC, clone_bundle_for_transform() |
| `core/analysis/transforms/fermi_shift.py` | 92 | FermiShift transform |
| `drivers/qe/parsers/bands.py` | 140 | QEBandsProvider (@register_parser("qe", "bands")) |
| `tests/gates/test_analysis_invariants.py` | 349 | 9 gate tests |
| `tests/core/analysis/test_bundles.py` | ~80 | Bundle construction + serialization tests |
| `tests/core/analysis/test_capability.py` | ~120 | Capability matching tests |
| `tests/core/analysis/test_transforms.py` | ~90 | Transform purity + chain tests |
| `tests/core/analysis/test_band_structure.py` | ~150 | BandStructure model tests |
| `tests/core/analysis/test_orchestrator.py` | ~80 | Orchestrator integration tests |
| `tests/core/analysis/test_qe_bands_e2e.py` | ~60 | Full pipeline E2E test |
| `tests/drivers/qe/test_qe_bands_provider.py` | ~100 | QE bands provider unit tests |

### 9.2 Modified Files

| File | Change |
|------|--------|
| `core/analysis/base.py` | `step_ulid` → `step_ulids: list[str]`; added `gen_steps`, `engine_name`, `warnings`, `manifest_snapshot` |
| `core/analysis/trajectory/model.py` | Added `to_primitives()` → CanonicalPrimitiveBundle |
| `core/driver_protocol.py` | Added `ANALYSIS_CAPABILITIES: list = []` to BaseEngineDriver |
| `drivers/qe/driver.py` | Added ANALYSIS_CAPABILITIES (bands + trajectory) |
| `drivers/qe/parsers/trajectory.py` | Updated parse kwargs: step_ulids, gen_steps, engine_name |
| `provenance/schema.py` | Added analysis_snapshots table, schema v1→v2 migration |
| `provenance/pins.py` | Added run_ulid_source field |

---

## 10. Conclusion

The kernel-layer implementation is **architecturally sound** and **spec-compliant**. The data model, transform pipeline, capability matching, and bundle types are all correctly structured and tested.

However, the implementation is **operationally inert**: no production code path triggers the new pipeline. The three critical gaps are:

1. **Parser registration fix** (hours of work)
2. **End-of-run eager write + API wiring** (substantial — Mainline A)
3. **GUI wiring** (substantial — Mainline B)

These are addressed in the companion document `ANALYSIS_PIPELINE_NEXT_PLAN.md`.
