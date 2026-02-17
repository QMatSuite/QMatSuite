# Worklog: Post-Compat-Removal Wiring Fixes

**Date**: 2026-02-16
**Plan**: `docs/history/plans/POST_COMPAT_REMOVAL_WIRING_PLAN.md`

## Approach Change

Original plan called for stripping GUI fields and simplifying TS types. User rejected this — GUI must look identical to before. Approach changed to **enriching backend responses** so the daemon provides all fields the GUI expects.

Key constraints enforced:
- Daemon must NOT import kernel — only `quantumvitas.api`
- Minimal new API surface — reuse existing `get_detail()` instead of adding `list_enriched()`
- ULID-based resolution — slug/filename resolve only at boundaries

## Progress

### Backend Enrichment (replaces Steps 1-4)
- [x] `_handle_list_calculations` in `server.py` now calls `svc.calculation.get_detail(calc_ulid)` per calc (full GUI-ready shape)
- [x] `get_detail()` in `service.py` now includes `calc_ulid`, `step_file`, `slug`, `species_map` in response
- [x] `list_demo_projects()` now includes `recommended_use`, `recommended_analysis`, `difficulty`, `estimated_runtime_scf`
- [x] `_handle_create_demo_project` enriched with `project_id`, `project_name`, `structure`, `calculation`, `ready_to_run`

### Step 5: TypeScript build check
- [x] `npx tsc --noEmit` passes (no type errors)

### Step 6: Write backend test
- [x] `tests/api/test_structure_import_pipeline.py` — 19 tests
  - 5 classes: TestSiImport (5), TestAlImport (3), TestSiMaterializeQE (5), TestAlMaterializeQE (4), TestDedupFingerprint (2)
  - Numerical assertions: lattice params (a/b/c, alpha/beta/gamma), frac coords, cell vectors, namelist values, kpoints
  - Parses actual QE .in output (CELL_PARAMETERS, ATOMIC_POSITIONS, namelists, K_POINTS)
  - Si diamond: a≈3.84Å, 60° angles, 2 atoms at (0,0,0) and (0.75,0.75,0.75)
  - Al FCC: a≈2.86Å, 60° angles, 1 atom at origin

### Step 7: Run Python tests
- [x] All 5594+ tests pass, 18 skipped

---

## Files Modified

| File | Change |
|------|--------|
| `src/quantumvitas/daemon/server.py` | `_handle_list_calculations` calls `get_detail` per calc; `_handle_create_demo_project` enriched |
| `src/quantumvitas/api/service.py` | `get_detail` adds `calc_ulid`, `step_file`, `slug`, `species_map`; `list_demo_projects` adds meta fields |
| `tests/api/test_structure_import_pipeline.py` | NEW — 19 tests, CIF→JSON→QE pipeline with numerical assertions |
