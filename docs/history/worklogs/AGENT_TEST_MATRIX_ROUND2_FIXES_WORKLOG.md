# Agent Test Matrix Round 2 — Remaining Fixes + Round 3 Worklog

**Date**: 2026-02-21
**Branch**: v2-python
**Scope**: Fix 3 remaining issues from Round 2 REVIEW, expand test matrix to 1+16, run Round 3

---

## Plan

### Part 1: Magnetization pipeline fix
- Root cause: `parse_scf_output_text()` in `analysis/parsers.py` NEVER extracts `total_magnetization` / `absolute_magnetization` from QE output text — the regex loop has no patterns for magnetization lines. Also, `SCFResult.to_dict()` doesn't include the fields. Even though `QESCFDigest` and `_build_summary()` code is present, the source data is always `None`.
- **Fix**: Add regex patterns `r"total magnetization\s*=\s*([-\d.]+)\s*Bohr"` and `r"absolute magnetization\s*=\s*([-\d.]+)\s*Bohr"` to the loop, add variables, add to `return SCFResult(...)`, add to `SCFResult.to_dict()`

### Part 2a: xTB energy in `_build_summary()`
- Root cause: `XTBDigest.to_dict()` (using `asdict()`) produces keys `"final_energy_eV"` and `"final_energy_Ha"` (Python field names verbatim). `_build_summary()` checks `"total_energy_ev"` and `"total_energy_ha"` (different names). Also `converged`, `n_iterations`, `total_wall_time_s` are xTB-specific field names.
- **Fix**: Add fallback checks in `_build_summary()` for xTB-specific field names

### Part 2b: xTB promote_structure
- Root cause: `save_relax_final_structure` in `service.py` uses `CalculationFileNaming.output_filename("relax")` = `"relax.out"` (QE convention), but xTB writes `xtb.out` + `xtbopt.xyz`. The geometry extraction also uses QE-specific functions.
- **Fix**: Detect xTB engine from `step_type_spec` (e.g. `"xtb_relax"`), fall back to `xtbopt.xyz`, use pymatgen's xyz reader for geometry

### Part 3: Test matrix expansion to 1+16
- 8 new tasks (09-16) targeting: Fe magnetization validation (fix 1), xTB promote fix (fix 2), ORCA (binary-not-installed error enrichment test), deliberately failing SCF (BUG-4/5 runtime test), Si vc-relax, Al DOS, Mg HCP SCF, convergence study

---

## Implementation Log

### Part 1: Magnetization fix — `analysis/parsers.py` — DONE

Root cause confirmed: `parse_scf_output_text()` has no magnetization regex.

QE output format:
```
     total magnetization       =     4.47 Bohr mag/cell
     absolute magnetization    =     4.47 Bohr mag/cell
```

Changes:
- Added `total_mag_pattern` and `abs_mag_pattern` regex
- Added `total_magnetization` and `absolute_magnetization` local variables (init None)
- Added extraction in loop (last occurrence wins — correct for relax/md where multiple SCF cycles run)
- Added both fields to `return SCFResult(...)` call
- Added both fields to `SCFResult.to_dict()` return dict

### Part 2a: xTB `_build_summary()` aliases — `get_results_summary.py` — DONE

Changes to `_build_summary()`:
- Energy: also check `"final_energy_eV"` (xTB's key) and `"final_energy_Ha"` (converted to eV)
- `converged`: also check `digest.get("success")` and `digest.get("converged_geometry")`
- `n_iterations`: also check `"n_opt_cycles"` (xTB geometry optimizer cycles)
- `wall_time_seconds`: also check `"wall_time_s"` (xTB field name)
- `homo_lumo_gap_eV`: mapped to `fermi_energy_eV` in summary (best proxy for xTB)

### Part 2b: xTB `promote_structure` — `api/service.py` — DONE

Changes in `save_relax_final_structure`:
- Detect engine from `step_type_spec` prefix (using `prefix_from`)
- If engine is `"xtb"`: look for `xtbopt.xyz` in raw_dir, use pymatgen `Structure.from_file()` to read geometry
- If engine is not `"xtb"`: use existing QE code path (`relax.out` + `read_final_geometry_from_output_text`)
- Error message: specific message for xTB if `xtbopt.xyz` is missing

### Part 3: Test matrix expansion — DONE

8 new tasks (09-16):
- 09: Fe BCC magnetization verification (validates Part 1 fix)
- 10: xTB water optimize + promote_structure (validates Part 2 fix)
- 11: QE Si vc-relax (variable-cell) + promote + bands
- 12: ORCA water single-point (tests error enrichment if ORCA not installed)
- 13: Deliberately failing QE SCF (ecutwfc=1, maxstep=2) — tests BUG-4/5 runtime
- 14: Al FCC DOS
- 15: Mg HCP SCF (hexagonal structure, different from BCC/FCC)
- 16: Si convergence study (compare ecutwfc=20 vs 40 Ry)

Updated `tools/agent_test_matrix.sh`:
- Phase 2 now launches 16 parallel agents (01-16)
- Summary checks 17 tasks total

---

## Test Results

TBD after Round 3 run

---

## Files Modified

### Source fixes
- `src/quantumvitas/analysis/parsers.py` — Part 1 (magnetization extraction)
- `src/quantumvitas/mcp/tools/get_results_summary.py` — Part 2a (xTB aliases in _build_summary)
- `src/quantumvitas/api/service.py` — Part 2b (xTB promote_structure)

### Test matrix
- `tools/agent_test_matrix.sh` — Part 3 (expand to 1+16)

### Worklog
- `docs/history/worklogs/AGENT_TEST_MATRIX_ROUND2_FIXES_WORKLOG.md` — this file
