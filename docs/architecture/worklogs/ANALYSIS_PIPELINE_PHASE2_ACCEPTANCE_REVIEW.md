# Analysis Pipeline — Phase 2 Acceptance Review

**Reviewer:** Claude Opus 4.6 (senior architect role)
**Date:** 2026-02-08
**Scope:** Codex work completing all 17 steps (G1–G5, A1–A7, B1–B5) + post-plan contract alignment
**Baseline:** `ANALYSIS_PIPELINE_NEXT_PLAN.md` in this directory
**Final reported result:** 4636 passed, 19 skipped

---

## 1. Spec Compliance Checklist

| ID | Invariant | File(s) | Key Symbol(s) | Pass? |
|----|-----------|---------|---------------|-------|
| Inv-A2 | Every AnalysisObject has `meta: AnalysisObjectMeta` | `core/analysis/band_structure.py`, `core/analysis/trajectory.py` | `BandStructure.meta`, `Trajectory.meta` | PASS |
| Inv-A4 | `to_primitives()` deterministic, parameterless, excludes `created_at` | gate: `test_canonical_bundle_deterministic`, `test_to_primitives_is_parameterless` | — | PASS |
| Inv-A5 | Derived bundles never cached | gate: `test_derived_never_cached` | — | PASS |
| Inv-A6 | `RenderMeta` excludes provenance fields | gate: `test_render_meta_no_provenance` | `RenderMeta` | PASS |
| Inv-A7 | Transform modules never import drivers | gate: `test_transform_no_engine_imports` | `transforms/fermi_shift.py` | PASS |
| Inv-A9 | No lazy payload wrappers in analysis core | gate: `test_no_lazy_payloads` | — | PASS |
| Inv-A10 | No disk-cache writes in analysis core (except `cas_writer.py`) | gate: `test_no_analysis_disk_cache` | — | PASS |
| Inv-A11a | Derived bundles never persisted to CAS | gate: `test_derived_never_persisted` | `write_canonical_to_cas` | PASS |
| Inv-A11b | Operational `get_analysis` never reads CAS | gate: `test_operational_path_no_cas_read` | `_derive_canonical_for_run_object` | PASS |
| Inv-A11c | CAS is content-addressed (SHA-keyed) | gate: `test_cas_is_content_addressed` | `analysis_snapshots` DDL | PASS |
| Inv-A12 | Frontend never imports kernel | gate: `test_frontend_no_kernel_import` | — | PASS |
| Inv-A13 | No engine branching in orchestrator/bundles/transforms | gate: `test_no_engine_branching_in_orchestrator` | — | PASS |
| Inv-A14 | No `.tmp/` refs in runtime paths | gate: `test_no_tmp_corpus_in_runtime` | — | PASS |
| §5.2 | Engines with analysis providers declare ANALYSIS_CAPABILITIES | gate: `test_analysis_capability_declaration` | QE: 2 caps, VASP: 0 (no providers) | PASS |
| §5.3a | Capability matching deterministic | gate: `test_capability_match_deterministic` | `find_contiguous_match` | PASS |
| §5.3b | Overlapping capabilities produce one bundle | gate: `test_no_redundant_canonical` | `run_post_run_analysis` | PASS |
| — | Unknown parser resolution warns/errors | gate: `test_unknown_engine_analysis_raises` | — | PASS |
| — | History world independence | gate (existing): provenance deletion leaves project runnable | — | PASS |

**Gate test count:** 18 (up from 9 before Codex's work). All in `tests/gates/test_analysis_invariants.py`.

---

## 2. Component Status Matrix

| Component | File(s) | Status | Notes |
|-----------|---------|--------|-------|
| **Parser registry** | `parsers/registry.py` | DONE | 14 registered: 12 `scf_digest` + QE `bands` + QE `trajectory` |
| **QE parser chain** | `drivers/qe/parsers/__init__.py` | FIXED (G1) | Now imports `bands.py` + `trajectory.py` |
| **QE bands provider** | `drivers/qe/parsers/bands.py:18` | DONE | `@register_parser("qe", "bands")` → `QEBandsProvider` |
| **QE trajectory provider** | `drivers/qe/parsers/trajectory.py:25` | DONE | `@register_parser("qe", "trajectory")` |
| **QE ANALYSIS_CAPABILITIES** | `drivers/qe/driver.py:17` | DONE | `bands` (seq: bandspw) + `trajectory` (seq: relax) |
| **Orchestrator** | `core/analysis/orchestrator.py` | DONE | `run_post_run_analysis()` — engine-agnostic |
| **CAS writer** | `core/analysis/cas_writer.py` | DONE | `write_canonical_to_cas()` + `write_analysis_snapshot_row()` |
| **Bundles** | `core/analysis/bundles.py` | DONE | `CanonicalPrimitiveBundle`, `DerivedPrimitiveBundle`, `compute_canonical_sha()` |
| **Transforms** | `core/analysis/transforms/fermi_shift.py` | DONE | `FermiShift.apply()` |
| **Staleness check** | `core/analysis/base.py:155` | DONE | `check_staleness(meta, calc_dir=)` — size+mtime |
| **Eager pipeline** | `api/service.py:312` | DONE | `_finalize_run_analysis_pipeline()` → digest rows + CAS snapshots |
| **Digest persistence** | `api/service.py:153` | DONE | `_persist_step_digest_rows()` — CAS tier-1 |
| **Snapshot persistence** | `api/service.py:231` | DONE | `_persist_eager_analysis_snapshots()` |
| **Surface A: Raw viewer** | `api/service.py:1682,1760` | DONE | `list_raw_files()` + `read_raw_file()` |
| **Surface B: Step digest** | `api/service.py:1780` | DONE | `get_step_digest()` — SQLite `run_steps` → CAS |
| **Surface C: Analysis viz** | `api/service.py:1823` | DONE | `get_analysis()` — operational derivation + transforms |
| **Snapshot replay** | `api/service.py:1854` | DONE | `get_analysis_snapshot()` — SQLite → CAS gzip blob |
| **Daemon RPC: new** | `daemon/server.py:4797–4874` | DONE | 5 new handlers wired |
| **Contract crawler** | `tests/contract_crawler/` | DONE | 5 exemptions with rationale |
| **SQLite schema** | `provenance/schema.py` | DONE | `analysis_snapshots` table with `UNIQUE(run_ulid, object_type)` |
| **Test fixtures** | `tests/data/analysis_bands/` | DONE | `si.bands.dat.gnu` + `si.3_bands.pp.out` |
| **Test helper** | `tests/api/_analysis_pipeline_test_utils.py` | DONE | `setup_qe_bands_run()` |

---

## 3. Remaining Gaps / Risks

### 3.1 Legacy Analysis Pipeline Still Active (HIGH)

The old `analysis/artifacts.py` (701 lines, marked DEPRECATED) is still **actively imported and called** from `service.py`:

| Legacy method in `Analysis` inner class | Lines | What it imports |
|----------------------------------------|-------|-----------------|
| `get_summary()` | 512–561 | `read_artifact, AnalysisType` |
| `list_properties()` | 563–609 | `artifact_exists, AnalysisType` |
| `get_property_ref()` | 611–706 | `get_artifact_path, read_artifact, AnalysisType` |
| `load_artifact()` | 708–798 | (uses `get_property_ref` output) |
| `get_band_structure_data()` | 1122+ | `AnalysisType, read_artifact, parse_bands_gnu` |
| `get_dos_data()` | 1945+ | `AnalysisType, read_artifact, parse_dos_data` |
| `get_scf_convergence_data()` | 1224+ | `AnalysisType, read_artifact, parse_scf_output` |
| `ensure_analysis()` | 1866–1943 | Calls the three above |

Total: **16 import sites** from `quantumvitas.analysis.*` in `service.py`.

Daemon legacy handlers still registered (lines 358–364):
- `ensure_calculation_analysis` → `_handle_ensure_calculation_analysis` (line 4608)
- `get_scf_convergence` → `_handle_get_scf_convergence` (line 4682)
- `get_dos_data` → `_handle_get_dos_data` (line 4704)
- `get_band_structure_data` → `_handle_get_band_structure_data` (line 4728)

**Risk:** Two parallel analysis pipelines coexist. GUI may still call legacy handlers. Must be cleaned before they drift.

### 3.2 `analysis/dos.py` — Dead Module (LOW)

`analysis/dos.py` is marked DEPRECATED and has **zero imports anywhere** in the codebase. It should be deleted as part of legacy cleanup.

### 3.3 No Daemon-Level E2E Test for New Pipeline (HIGH)

All new analysis pipeline tests operate at the `QVService` level:
- `tests/api/test_analysis_eager_write.py` — calls `_finalize_run_analysis_pipeline()` directly
- `tests/api/test_analysis_endpoint.py` — calls `get_analysis()` directly
- `tests/api/test_analysis_snapshot_endpoint.py` — calls `get_analysis_snapshot()` directly

**No test exercises the full daemon RPC path**: daemon → QVService → runner → analysis pipeline → CAS/SQLite.

The "ancient" test (`tests/daemon/test_si_bands_calculation_daemon.py`) **only tests the legacy pipeline** — it calls `get_band_structure_data` and `analyze_band`, not the new Surface B/C endpoints.

### 3.4 VASP Has Zero Analysis Capabilities (MEDIUM)

`VASPDriver` (line 19, `drivers/vasp/driver.py`):
- Has `bandspw` in `SUPPORTED_GEN_STEPS`
- Has `bands` in `get_capabilities()`
- Has `EIGENVAL` in `get_artifact_patterns()`
- Has **NO** `ANALYSIS_CAPABILITIES` attribute
- Has **NO** `@register_parser("vasp", "bands")` provider

VASP is the second-most-mature engine in the codebase (Phase B1 complete), but analysis is entirely absent.

### 3.5 No Second Engine Validates the Universal Pipeline

The entire analysis pipeline — from capability matching through CAS persistence — has only been tested with QE. Without a second engine proving universality, the "engine-agnostic" claim is aspirational.

---

## 4. Test Coverage Assessment

### 4.1 What Exists (Good)

| Test file | Count | Scope |
|-----------|-------|-------|
| `tests/gates/test_analysis_invariants.py` | 18 | Static invariant enforcement |
| `tests/core/analysis/test_qe_bands_e2e.py` | ~5 | Kernel E2E: raw → BandStructure → canonical → FermiShift → derived |
| `tests/api/test_analysis_eager_write.py` | ~5 | CAS + SQLite persistence after `_finalize_run_analysis_pipeline` |
| `tests/api/test_analysis_endpoint.py` | ~5 | Operational `get_analysis()` returns bundle, transforms work |
| `tests/api/test_analysis_snapshot_endpoint.py` | ~5 | Replay `get_analysis_snapshot()` reads CAS |
| `tests/api/test_analysis_capabilities.py` | ~5 | Legacy `ensure_analysis` integration |
| Other analysis tests | ~20 | Various unit tests |
| **Total analysis tests** | **~63** | — |

### 4.2 What Is Missing

1. **Golden daemon-level E2E test** — Actually runs QE (si_bands_demo), asserts on digest rows + CAS blobs + `get_analysis()` response. Does NOT exist.
2. **Second-engine analysis test** — No non-QE engine exercises the pipeline end-to-end.
3. **Legacy deletion test** — Nothing verifies that legacy imports are removed after cleanup.
4. **Staleness invalidation test** — `check_staleness` is implemented but no test validates it triggers re-derivation when source files change.

---

## 5. Verdict

**Phase 2 (Codex work): ACCEPTED with caveats.**

The implementation is spec-compliant across all 18 gate tests. The kernel analysis layer is architecturally sound: engine-agnostic orchestrator, content-addressed CAS, deterministic canonical bundles, operational/replay separation. The API wiring is complete for all three GUI surfaces plus eager persistence.

**However:** The legacy analysis pipeline remains fully active, no daemon-level golden test exists, and VASP (the second-most-important engine) has zero analysis support. These gaps must be closed in Phase 3.
