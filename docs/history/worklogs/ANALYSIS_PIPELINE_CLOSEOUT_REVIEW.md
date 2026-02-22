# Analysis Pipeline Close-Out Acceptance Review

**Date:** 2026-02-06
**Reviewer:** Claude Opus (senior architect audit)
**Scope:** Phase 3 completion — QE golden daemon, VASP golden daemon, legacy removal, gate enforcement

---

## 1. Verification Summary

### Full Test Suite

```
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
# Result: 4584 passed, 19 skipped (19 skipped are expected — ORCA, PySCF, QMCPACK markers)
```

### QE Golden Daemon Test

```
source .venv/bin/activate && python -m pytest tests/daemon/test_si_bands_golden_daemon.py -v --tb=short
# Result: 1 passed (~60s, actually runs QE pw.x + bands.x)
```

**What it exercises:**
- `create_demo_project` → `si_bands_demo` scaffold with `project.qms.yml`
- `list_calculations` → finds `si-bands` slug
- `run_calculation` → executes 4 steps (scf → nscf → bandspw → bandspp)
- `get_step_digest` → per-step SHA256 digest from CAS (all 4 steps)
- `list_raw_files` → confirms `*.bands.dat.gnu` in bandspw step
- `get_analysis` → produces `CanonicalPrimitiveBundle` with `object_type=bands`
  - Bundle assertions: `series` is non-empty list, `provenance_meta.run_ulid` matches, `provenance_meta.step_ulids` non-empty
- `get_analysis_snapshot` → returns same `canonical_sha` as `get_analysis`
- **SQLite verification:** direct `SELECT canonical_sha, object_type FROM analysis_snapshots WHERE run_ulid = ?` confirms exactly 1 row with matching SHA
- **CAS blob verification:** `.provenance/.cas/analysis/<sha>.json.gz` exists and contains `object_type=bands`

### VASP Golden Daemon Test

```
source .venv/bin/activate && python -m pytest tests/daemon/test_vasp_bands_golden_daemon.py -v --tb=short
# Result: 1 passed (~8.78s, runs real VASP with local installation)
```

**Skip logic:** `_require_real_vasp()` fixture auto-skips when:
- `CI=true` environment variable is set
- VASP binary not found or is fake_vasp.py script
- VASP binary has missing dynamic libraries
- Si POTCAR not found at expected path

**What it exercises:**
- `create_demo_project` → `si_bands_vasp_demo` scaffold
- `run_calculation` → 2 steps (vasp_scf + vasp_bandspw)
- `get_step_digest` → per-step SHA256 digests (both steps)
- `list_raw_files` → confirms `{EIGENVAL, KPOINTS, OUTCAR, vasprun.xml}` in bandspw step
- `get_analysis` → produces `CanonicalPrimitiveBundle` with `object_type=bands`
  - **Array assertions:** `k_distances` monotonically non-decreasing, `len(k_distances) >= 8`, eigenvalues shape consistent
  - **Physical sanity:** energy range > 4 eV, min energy < -1 eV, max energy > 1 eV
  - **Labels:** first label in `{G, Γ}`, last label in `{L, Γ, G}`
  - **Series:** `n_bands >= 8`, series count matches n_bands
- `get_analysis_snapshot` → same `canonical_sha`
- **SQLite verification:** exactly 1 row by `run_ulid`, matching SHA and `object_type=bands`
- **CAS blob:** `.provenance/.cas/analysis/<sha>.json.gz` exists and round-trips to `object_type=bands`

### Gate Tests

```
source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py -v --tb=short
# Result: 19 passed
```

All 19 gate tests enforce constitutional invariants including:
- `test_no_legacy_analysis_artifact_imports` — confirms `analysis/artifacts.py` is not imported anywhere in runtime code
- `test_operational_path_no_cas_read` — confirms `get_analysis` operational path never reads CAS
- `test_derived_never_persisted` — confirms API never writes derived bundles to CAS
- `test_cas_is_content_addressed` — confirms SQLite schema uses `canonical_sha TEXT NOT NULL` with `UNIQUE(run_ulid, object_type)`

---

## 2. CI Behavior

| Test | CI Status | Mechanism |
|------|-----------|-----------|
| QE golden daemon | **Runs in CI** | Marked `pytest.mark.qe_core`; CI filter is `-m "not requires_orca and not requires_pyscf"` which does NOT exclude `qe_core` |
| VASP golden daemon | **Auto-skips in CI** | `_require_real_vasp()` fixture checks `CI` env var and binary availability |
| Gate tests (19) | **Runs in CI** | No skip markers; pure Python AST inspection |
| 19 skipped tests | **Expected** | `requires_orca` (14), `requires_pyscf` (3), `requires_qmcpack` (2) — all external binary dependencies |

---

## 3. Provenance Compliance

### Operational/Replay Boundary (Inv-A11)

- **Operational path** (`get_analysis`): derives bundles from present raw evidence via `run_post_run_analysis()`. Gate test `test_operational_path_no_cas_read` confirms this path never calls `_load_snapshot_bundle`, `retrieve`, or `retrieve_json`.
- **Replay path** (`get_analysis_snapshot`): reads from SQLite `analysis_snapshots` table, then loads CAS blob by `canonical_sha`. This is a separate code path.
- **Eager persistence** (`_persist_eager_analysis_snapshots`): writes canonical bundle to CAS and linkage row to SQLite during `_finalize_run_analysis_pipeline()`. Non-fatal on failure (try/except with warning).

### SQLite Scoping

Both golden tests query SQLite by `run_ulid`:
```sql
SELECT canonical_sha, object_type FROM analysis_snapshots WHERE run_ulid = ?
```
This is thread-safe and test-isolated — each daemon test uses `tmp_path` (auto-cleaned by pytest).

### CAS Content-Addressing

- `write_canonical_to_cas()` computes `canonical_sha = compute_canonical_sha(bundle)` from deterministic JSON serialization
- File path: `<cas_dir>/<sha>.json.gz`
- Idempotent: if blob exists, returns early without writing
- Atomic write: uses `.tmp` suffix then `replace()`

---

## 4. Legacy Removal Confirmation

| Item | Status | Evidence |
|------|--------|---------|
| `analysis/artifacts.py` | **Deleted** | File does not exist on disk |
| Gate enforcement | **Active** | `test_no_legacy_analysis_artifact_imports` scans all runtime code in `api/`, `daemon/`, `core/` for any reference to `qmatsuite.analysis.artifacts` |
| Legacy API methods | **Deleted** | `get_summary`, `list_properties`, `ensure_analysis`, `get_band_structure_data`, `get_dos_data`, `get_scf_convergence_data` all removed from `service.py` |
| New API surface | **Active** | `list_raw_files`, `read_raw_file`, `get_step_digest`, `get_analysis`, `get_analysis_snapshot` — all use the new pipeline |

---

## 5. Architecture Verified

### Pipeline Flow (proven by both golden tests)

```
Daemon RPC "run_calculation"
  → Runner executes steps
  → _finalize_run_analysis_pipeline(calculation, run_result)
    → _persist_step_digest_rows()      [CAS tier-1 + SQLite run_steps]
    → _persist_eager_analysis_snapshots()
      → run_post_run_analysis()        [kernel-only: capability match → provider.parse → to_primitives]
      → write_canonical_to_cas()       [gzip JSON to .provenance/.cas/analysis/<sha>.json.gz]
      → write_analysis_snapshot_row()  [SQLite: (run_ulid, object_type) → canonical_sha]
```

### Engine Extension Pattern (proven by VASP bands)

1. Driver declares `ANALYSIS_CAPABILITIES` with `gen_step_sequence` and `evidence_files`
2. Provider class uses `@register_parser(engine, object_type)` decorator
3. Provider implements `can_parse(raw_dir) -> bool` and `parse(raw_dir, calc_dir, **kwargs) -> AnalysisObject`
4. No changes needed to orchestrator, CAS writer, or service layer

---

## 6. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Golden test files accidentally deleted | Low | Add gate test `test_golden_daemon_tests_exist` (this close-out adds it) |
| VASP golden test silent skip if binary changes | Low | `_check_real_vasp_resources()` validates binary, rejects fake, checks POTCAR |
| CAS blob disk growth | Very Low | Content-addressed dedup prevents duplicate blobs for identical runs |
| SQLite schema migration | Low | `write_analysis_snapshot_row()` auto-adapts to columns present via `PRAGMA table_info` |
| No DOS analysis object yet | Info | Only bands implemented for QE + VASP; DOS is next logical extension (playbook covers this) |

---

## 7. Verdict

**ACCEPT.** All Phase 3 deliverables are complete and verified:
- QE golden daemon test passes end-to-end (actually runs QE)
- VASP golden daemon test passes end-to-end (actually runs VASP)
- Legacy `artifacts.py` deleted with gate enforcement
- 19 gate tests pass, covering all constitutional invariants
- 4584 tests pass, 19 expected skips
- CI correctly includes QE golden test and auto-skips VASP golden test
