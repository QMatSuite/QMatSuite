# Agent Test Matrix Round 1 — Bug & Gap Fixes Worklog

**Date**: 2026-02-21
**Branch**: v2-python
**Scope**: Fix 5 bugs, 8 information gaps, and supporting updates identified from agent test matrix trace analysis

---

## Plan

### Part A: Fix 5 Bugs

1. **BUG-1**: `apply_preset` returns success when steps_updated=0
2. **BUG-2**: `promote_structure` missing "minimize" in relax type set + stale "vc-relax"/"vc_relax" refs
3. **BUG-3**: `get_results_summary` only uses QE parser (not engine-agnostic)
4. **BUG-4**: `quick_run` missing error enrichment on failure
5. **BUG-5**: `get_status` never detects failures (has_failed always False)

### Part B: Fix Information Gaps

1. **GAP-1**: Magnetization missing from QESCFDigest + results summary
2. **GAP-3**: No `list_calculations` MCP tool
3. **GAP-5/6/7**: Missing instructions in `.mcp.json.example`
4. **GAP-8**: Demo load_demo context_hint doesn't mention species_map status

### Part C: Update `.mcp.json.example` instructions
### Part D: Audit demo ecutwfc values (qe_si_scf uses 20 Ry → raise to 30 Ry)
### Part F: Update deferred items

### Implementation Order

1. BUG-2 → 2. BUG-5 → 3. BUG-1 → 4. GAP-1+BUG-3 → 5. BUG-4 → 6. GAP-3 → 7. GAP-8 → 8. Part C → 9. Part D → 10. Part F

---

## Implementation Log

### BUG-2: promote_structure + vc-relax cleanup — DONE
- `promote_structure.py`: `_RELAX_GEN_TYPES = frozenset({"relax", "minimize"})`, error messages updated
- `run_calculation.py`: `_is_relax_workflow` → `{"relax", "minimize"}`
- `get_status.py`: `gen_types & {"relax", "minimize"}`
- `quick_run.py`: `workflow in {"relax", "minimize"}`
- `get_results_summary.py`: `step_type_gen in {"relax", "minimize"}`
- `error_enrichment.py`: `workflow in ("relax", "minimize")`
- Verified: no remaining vc-relax/vc_relax refs in MCP tools (only knowledge base entries, which are correct)

### BUG-5: get_status failure detection — DONE
- Added output file check after `get_latest_run_for_step()` returns no successful run
- If `raw_dir` contains `.out` or `.log` files but no successful run → mark as "failed"
- Added "failed" status hint with diagnostic guidance
- Added dedicated hint for `overall_status == "failed"`

### BUG-1: apply_preset steps_updated=0 — DONE
- Now checks `steps_updated == 0` and `has_errors` (error status in step_results)
- Returns `make_error("preset_partial_failure", ...)` with diagnostics when actual errors occurred
- Returns success with warning when steps are skipped (non-receiver) but no errors — this is normal for some preset dimensions

### GAP-1 + BUG-3: Magnetization + engine-agnostic parser — DONE
- `QESCFDigest`: Added `total_magnetization` and `absolute_magnetization` fields, populated from `SCFResult`
- `get_results_summary._parse_direct()`: Now uses `find_parser_for_raw()` from parser registry with `import quantumvitas.drivers` trigger, falls back to QE parser
- `get_results_summary._build_summary()`: Multi-unit support: `total_energy_ev` (VASP/xTB), `total_energy_ry` (QE), `total_energy_ha` (ORCA/Gaussian) → all convert to `total_energy_eV`. Added `_HA_TO_EV = 27.211386245988`
- Magnetization fields included in summary when present
- `run_calculation._try_parse_digest()`: Same engine-agnostic pattern applied

### BUG-4: quick_run error enrichment — DONE
- Mirrored `run_calculation.py` pattern: error enrichment via `enrich_run_error()`
- Added "completed but not converged" check
- Added failure path with `enrich_run_error()` + fallback to basic error
- Added `_try_parse_digest()` helper (same engine-agnostic pattern)
- Step summaries now include `message` field

### GAP-3: list_calculations MCP tool — DONE
- New file: `src/quantumvitas/mcp/tools/list_calculations.py`
- Follows `list_structures.py` pattern exactly
- Uses `svc.calculation.list()` → returns `CalculationDTO` list
- Fields: `calc_ulid`, `name`, `engine`, `status`, `n_steps`, `structure_ulid`
- Wired in `server.py` after `inspect_calculation`

### GAP-8: Demo context hint — DONE
- `load_demo` context_hint now includes: "Species map is pre-configured from the demo — no need to call set_species_map or auto_resolve_species_map."
- Also added `inspect_calculation(dry_run=True)` emphasis before `run_calculation`

### Part C: .mcp.json.example instructions — DONE
Added 7 new instruction lines:
1. `generate_kpath()` for band structure workflows
2. `quick_run()` single-call shortcut
3. `list_calculations()` check before duplicates
4. `search_knowledge()` proactive use
5. Post-run analysis with `list_analyses()` + `plot_analysis()`
6. `inspect_calculation(dry_run=True)` emphasis (reinforced)

### Part D: Demo ecutwfc audit — DONE
- `qe_si_scf.yml`: ecutwfc 20.0 → 30.0
- Updated `.generator_manifest.json` output_checksum for qe_si_scf
- All other QE demos already use 30+ Ry — no changes needed

### Part F: Deferred items update — DONE
- Updated "Parser auto-registration chain" item with partial fix note
- Added "Agent Test Matrix Round 1 fixes" section with completed items checklist
- Added remaining deferred items: demo ecutwfc validation gate test, history service failed run query

---

## Test Adjustments

- Tool count tests (3 files): 31 → 32 to account for new `list_calculations` tool
  - `test_stage_p1.py`: `test_tool_count_31` → `test_tool_count_32`
  - `test_stage_p2.py`: `test_31_tools` → `test_32_tools`
  - `test_stage11.py`: `test_all_31_tools_registered` → `test_all_32_tools_registered` + added `list_calculations` to expected_names set
- Demo checksum gate: Updated manifest checksum for `qe_si_scf` after ecutwfc change

---

## Test Results

**6445 passed, 4 skipped, 0 failed** (vs 6445 passed before changes — no regressions)

---

## Files Modified

### Source files (12)
- `src/quantumvitas/mcp/tools/promote_structure.py` — BUG-2
- `src/quantumvitas/mcp/tools/run_calculation.py` — BUG-2, BUG-3
- `src/quantumvitas/mcp/tools/get_status.py` — BUG-2, BUG-5
- `src/quantumvitas/mcp/tools/quick_run.py` — BUG-2, BUG-4
- `src/quantumvitas/mcp/tools/get_results_summary.py` — BUG-2, BUG-3, GAP-1
- `src/quantumvitas/mcp/tools/apply_preset.py` — BUG-1
- `src/quantumvitas/mcp/error_enrichment.py` — BUG-2
- `src/quantumvitas/mcp/tools/demo_store.py` — GAP-8
- `src/quantumvitas/mcp/tools/list_calculations.py` — GAP-3 (NEW)
- `src/quantumvitas/mcp/server.py` — GAP-3 wiring
- `src/quantumvitas/drivers/qe/parsers/output.py` — GAP-1

### Config/resource files (3)
- `.mcp.json.example` — Part C
- `resources/demo_projects/qe_si_scf.yml` — Part D
- `resources/demo_projects/.generator_manifest.json` — Part D checksum

### Test files (3)
- `tests/mcp/test_stage_p1.py` — tool count 31→32
- `tests/mcp/test_stage_p2.py` — tool count 31→32
- `tests/mcp/test_stage11.py` — tool count 31→32 + expected_names

### Doc files (2)
- `docs/plans/DEFERRED_ITEMS.md` — Part F
- `docs/history/worklogs/AGENT_TEST_MATRIX_ROUND1_FIXES_WORKLOG.md` — this file
