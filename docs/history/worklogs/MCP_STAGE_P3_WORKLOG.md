# Post-Phase 1 Polish Stage P3 — Worklog

**Status**: Complete
**Date**: 2026-02-19
**Prior stage**: P2 (resource discovery + auto-resolution, 26 tools)

## Summary

Stage P3 "Make it smooth" fixes 5 demo friction points without adding new tools
(tool count stays at 26). Key fixes: server auto-loads project on startup,
dry_run shows complete QE input files, presets work with advertised profile names,
CIF errors are helpful, and preflight has no false positives.

---

## Fix 1: Server Startup Auto-Load (CRITICAL)

**Root cause**: `_project_root_override = None` on startup; tools fail with `no_project`
if CWD is not inside a project.

**Fix**:
- Rewrote `init_project.py`: removed `path` parameter, now uses `QMATSUITE_PROJECT` env
  var (or CWD fallback). Idempotent — loads existing project or creates new one.
- Added startup auto-load block to `server.py`: tries `find_project_root()` from
  `QMATSUITE_PROJECT` before `mcp.run()`.

## Fix 2+7: dry_run Missing K_POINTS + Preflight False Positive (CRITICAL)

**Root cause**: dry_run and preflight only received `step_params` (parameters namelist),
not `cards` (K_POINTS, ATOMIC_SPECIES). K_POINTS lives in `step_detail["cards"]`.

**Fix**: Added `_merge_cards_into_params()` helper that:
1. Extracts K_POINTS from cards → `params["kpoints"]` dict
2. Injects `nat`/`ntyp` from structure_info into SYSTEM namelist
3. Called before both `write_engine_inputs()` (dry_run) and `checker.check()` (preflight)

Also updated `test_stage8.py::TestPreflightIntegration::test_inspect_includes_preflight_issues`
which was asserting the false positive behavior.

## Fix 3: apply_preset "Unknown MagnetismOption value: NM" (MEDIUM)

**Root cause**: `get_presets` returns profile names (`NM`, `COL`, etc.) from
`PROFILE_TO_ENUM` dict keys. But `_normalize_option()` in `compiler.py` matches
by `enum.value` (lowercase: `nonmagnetic`, `collinear_lsda`).

**Fix**: Added normalization in `apply_preset.py` that translates profile names
to enum values using `PROFILE_TO_ENUM` mapping before passing to service.

## Fix 4+6: CIF Error Hints + Context Hints (MEDIUM/LOW)

**Fix**:
- `import_structure.py`: CIF-specific error message with actionable hints
  (mentions `_atom_site_label`, POSCAR alternative, `search_demos()`)
- `list_engines.py`: context hint now mentions `search_demos()`
- `init_project.py`: context hint now mentions `search_demos()`

## Fix 5: Demo Structure Registration (NO BUG)

Investigation confirmed `load_demo_as_calculation()` correctly registers structures.
Tests added to verify.

---

## Test Results

```
tests/mcp/test_stage_p3.py: 14 passed
tests/mcp/test_stage_p1.py: 11 passed  (updated for init_project signature change)
tests/mcp/:             385 passed, 0 failed
Full suite:            6045 passed, 0 failed, 4 skipped
```

## Files Modified

- `src/quantumvitas/mcp/tools/init_project.py` — rewritten (remove path param, load-or-create)
- `src/quantumvitas/mcp/server.py` — added startup auto-load block
- `src/quantumvitas/mcp/tools/inspect_calculation.py` — merge cards into dry_run + preflight
- `src/quantumvitas/mcp/tools/apply_preset.py` — profile→enum normalization
- `src/quantumvitas/mcp/tools/import_structure.py` — CIF error hints
- `src/quantumvitas/mcp/tools/list_engines.py` — context hint update

## Files Created

- `tests/mcp/test_stage_p3.py` — 14 new tests

## Files Updated (existing tests)

- `tests/mcp/test_stage_p1.py` — init_project tests updated for new signature
- `tests/mcp/test_stage8.py` — preflight test updated (false positive resolved)
