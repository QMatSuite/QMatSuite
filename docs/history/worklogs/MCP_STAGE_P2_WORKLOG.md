# Post-Phase 1 Polish Stage P2 — Worklog

**Status**: Complete
**Date**: 2026-02-19
**Prior stage**: P1 (set_species_map, init_project, CIF errors, demo fix)

## Summary

Stage P2 adds resource discovery and auto-resolution so the MCP agent can
query what pseudopotentials/potentials exist and `quick_run` works
out-of-the-box for QE with Si (using internal pseudos, no SSSP install needed).

Two new MCP tools (`list_available_resources`, `auto_resolve_species_map`),
a shared internal helper module (`_resource_utils.py`), and enhancements to
four existing tools (`quick_run`, `create_calculation`, `run_calculation`,
`inspect_calculation`). Tool count: 24 → 26.

---

## Plan

### Problem

After P1, the agent can call `set_species_map` but must **guess** pseudopotential
filenames. There is no way to discover what's available, and `quick_run` requires
explicit `species_map` for pseudo engines (QE, ABINIT, Siesta). This creates
friction: the agent doesn't know what to put in `species_map`.

### Goals

1. **Resource discovery**: Agent can query what pseudos/potentials exist per engine.
2. **Auto-resolution**: Agent can auto-resolve species_map from the project's
   pseudo library (SSSP Precision by default, per decision D4).
3. **Friction elimination**: `quick_run` and `create_calculation` auto-resolve
   species_map when not provided (best-effort).
4. **Guard rails**: `run_calculation` rejects pseudo engine runs with no species_map
   (fail early with actionable hint instead of cryptic engine error).
5. **Visibility**: `inspect_calculation` shows resource readiness status.

### Architecture

```
_resource_utils.py (internal, not a tool)
  ├── auto_resolve_species_map_internal()  — calls core pseudo resolution
  └── check_resource_status()             — reports species_map readiness

list_resources.py (new MCP tool)
  └── list_available_resources(engine, elements)
        ├── QE: svc.project.get_pseudo_options(elements)
        ├── VASP: list_available_potcars(functional="PBE")
        ├── LAMMPS: get_default_potential_root() → list files
        ├── xTB/ORCA/Gaussian/Psi4/PySCF/GPAW: {resources_needed: false}
        └── CP2K/W90/QMCPACK/Yambo/Siesta/ABINIT: {managed: false}

resolve_species_map.py (new MCP tool)
  └── auto_resolve_species_map(calc_ulid, library, flavor)
        └── calls auto_resolve_species_map_internal → applies via update_species_map

Enhanced existing tools:
  quick_run.py        — auto-resolve if species_map not provided
  create_calculation  — auto-resolve at creation, dynamic hint
  run_calculation     — reject pseudo engines with empty species_map
  inspect_calculation — include resource_status in payload
```

### Key Backend APIs Reused

| Function | Location | Notes |
|----------|----------|-------|
| `resolve_project_pseudos` | `core/pseudo_config.py:1326` | Resolution chain: internal → project → store → seed |
| `PseudoResolutionRequest` | `core/pseudo_config.py:1301` | Defaults `flavor="efficiency"`, we override to `"precision"` (D4) |
| `load_pseudo_config` | `core/pseudo_config.py:161` | Loads from user config or returns defaults |
| `svc.project.get_pseudo_options` | `api/service.py:7491` | Wrapper for `get_pseudo_options_for_elements` |
| `list_available_potcars` | `drivers/vasp/engine/vasp_potcar.py:163` | Scans POTCAR library dirs |
| `get_default_potential_root` | `drivers/lammps/engine/lammps_potential.py:16` | Env var + repo root + walk-up |

### Execution Order

1. Append Section 7 (D1-D8 decisions) to `RESOURCE_MANAGEMENT_REVIEW.md`
2. Create `_resource_utils.py` (shared internal helpers)
3. Create `list_resources.py` + `resolve_species_map.py` (new tools)
4. Enhance `quick_run.py`, `create_calculation.py`, `run_calculation.py`, `inspect_calculation.py`
5. Wire in `server.py`, update `test_stage11.py` + `test_stage_p1.py`
6. Write `test_stage_p2.py`
7. Run tests: P2 → MCP → full suite

---

## Implementation Log

### Part 0: Review Document Update

Appended Section 7 "Architectural Decisions (2026-02-18)" to
`docs/history/reviews/RESOURCE_MANAGEMENT_REVIEW.md` after Section 6 (line 734).
Contains decisions D1–D8 verbatim from the task spec:

- **D1**: Platform-specific app data (not `~/.qmatsuite/`)
- **D2**: Program vs resources separation
- **D3**: External engine pointer mechanism (`engine.json`)
- **D4**: Auto-resolve uses SSSP Precision (not Efficiency)
- **D5**: Download requires user consent (client-side)
- **D6**: No agent self-download (must use QMatSuite tools)
- **D7**: Distribution strategy (Lite vs Full)
- **D8**: Micromamba placement

### Part 1: `_resource_utils.py` — Shared Internal Helpers

Created `src/qmatsuite/mcp/tools/_resource_utils.py`:

- `PSEUDO_ENGINES = ("qe", "abinit", "siesta")` — constant for pseudo engine check
- `auto_resolve_species_map_internal(calc_ulid, svc, library, flavor)`:
  - Gets calc detail → engine + elements
  - Returns `None` if engine not in PSEUDO_ENGINES or no elements
  - Calls `resolve_project_pseudos(config, request)` from core
  - On success: returns `{elem: {"pseudopot": filename}}` dict
  - On failure: returns `None` (caller decides error handling)
- `check_resource_status(calc_ulid, svc)`:
  - Returns `{species_map_set, all_pseudos_resolved, missing_elements, suggestion}`
  - Handles non-pseudo engines gracefully
  - Generates actionable suggestion text

### Part 2: `list_resources.py` — New MCP Tool

Created `src/qmatsuite/mcp/tools/list_resources.py`:

- `list_available_resources(engine, elements)` @mcp.tool
- Engine dispatch:
  - **QE**: Calls `svc.project.get_pseudo_options(elements)` — returns per-element
    variant count and example filenames. Default elements: Si, Al, C, H, O, Fe, Cu, Li, He
  - **VASP**: Calls `list_available_potcars("PBE")` — filters by element prefix if provided
  - **LAMMPS**: Uses `get_default_potential_root()` — lists files, capped at 50
  - **Builtin** (xTB, ORCA, Gaussian, Psi4, PySCF, GPAW): `{resources_needed: false}`
  - **Unmanaged** (CP2K, W90, QMCPACK, Yambo, Siesta, ABINIT): `{managed: false}`
  - **Unknown**: error with suggestions

**Bug found during testing**: Plan spec said `svc.species.get_pseudo_options()` but
the actual service attribute is `svc.project.get_pseudo_options()` (the method lives
in the `Project` inner class of QMSService). Fixed immediately.

### Part 3: `resolve_species_map.py` — New MCP Tool

Created `src/qmatsuite/mcp/tools/resolve_species_map.py`:

- `auto_resolve_species_map(calc_ulid, library, flavor)` @mcp.tool
- Validates calc exists, checks engine is in PSEUDO_ENGINES
- Calls `auto_resolve_species_map_internal()` from `_resource_utils`
- On success: applies via `svc.calculation.update_species_map()`, returns species_map
- On failure: returns error with hint about SSSP installation and internal pseudos

### Part 4: Enhanced Existing Tools

#### `quick_run.py`

Added auto-resolve block after `if species_map:` / before step addition:

```python
if not species_map:
    try:
        resolved = auto_resolve_species_map_internal(calc_ulid, svc)
        if resolved:
            svc.calculation.update_species_map(calc_ulid, resolved)
    except Exception:
        pass  # Best-effort
```

This means `quick_run(engine="qe", workflow="scf", structure_selector="Si")`
now works without `species_map` argument (auto-resolves from internal pseudos).

#### `create_calculation.py`

Added auto-resolve after step addition, before return:

- Attempts `auto_resolve_species_map_internal()` for QE/ABINIT/Siesta
- Sets `species_map_resolved` flag in response data
- Dynamic hint: if auto-resolved → "Species map auto-resolved. Use apply_preset..."
  else → "IMPORTANT: call auto_resolve_species_map or set_species_map..."

#### `run_calculation.py`

Added species_map validation between detail fetch and run:

```python
engine = detail.get("engine_family", "")
species_map = detail.get("species_map") or {}
if engine in ("qe", "abinit", "siesta") and not species_map:
    return make_error("missing_species_map", ...)
```

Removed duplicate `engine = detail.get(...)` that was later in the function
(now set once before validation, reused by both validation and enrichment).

#### `inspect_calculation.py`

Added resource status check after payload assembly, before step detail:

```python
try:
    from qmatsuite.mcp.tools._resource_utils import check_resource_status
    payload["resource_status"] = check_resource_status(calc_ulid, svc)
except Exception:
    pass
```

### Part 5: Server Wiring + Test Updates

#### `server.py`

Added two imports at the end:

```python
# Stage P2: resource management
import qmatsuite.mcp.tools.list_resources
import qmatsuite.mcp.tools.resolve_species_map
```

#### `test_stage11.py`

- Renamed `test_all_24_tools_registered` → `test_all_26_tools_registered`
- Updated expected count: 24 → 26
- Added `"list_available_resources"` and `"auto_resolve_species_map"` to expected names set
- Added new tool names to `tool_names` set in `test_no_dead_end_hints`

#### `test_stage_p1.py`

- Updated `test_create_calc_mentions_species_map` — now checks for either
  `"species_map"` or `"auto-resolved"` in hint (since auto-resolve changes the hint)
- Renamed `test_tool_count_24` → `test_tool_count_26`, updated count

### Part 6: `test_stage_p2.py` — 21 New Tests

Created `tests/mcp/test_stage_p2.py` with 7 test classes:

| Class | Tests | Notes |
|-------|-------|-------|
| `TestListAvailableResources` | 6 | QE+Si, QE defaults, VASP, LAMMPS, xTB builtin, unknown |
| `TestAutoResolveSpeciesMap` | 4 | QE resolve, metadata, bad ULID, unsupported engine |
| `TestQuickRunAutoResolve` | 2 | Auto w/o map, explicit map honoured (require QE) |
| `TestCreateCalcAutoResolve` | 2 | Auto-resolve flag, hint content |
| `TestRunCalcValidation` | 2 | Missing map error, with map no error |
| `TestInspectResourceStatus` | 2 | Key present, flags missing |
| `TestToolCount` | 1 | 26 tools, P2 tools in set |
| `TestContextHints` | 2 | list_resources hints, resolve hints |

---

## Test Results

```
tests/mcp/test_stage_p2.py:  21 passed
tests/mcp/ (full):           356 passed
tests/ (full suite):         6016 passed, 4 skipped, 0 failed
```

---

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `docs/history/reviews/RESOURCE_MANAGEMENT_REVIEW.md` | Modified | Appended Section 7 (D1-D8 decisions) |
| `src/qmatsuite/mcp/tools/_resource_utils.py` | Created | Internal helpers: auto_resolve + check_status |
| `src/qmatsuite/mcp/tools/list_resources.py` | Created | `list_available_resources` MCP tool |
| `src/qmatsuite/mcp/tools/resolve_species_map.py` | Created | `auto_resolve_species_map` MCP tool |
| `src/qmatsuite/mcp/tools/quick_run.py` | Modified | Auto-resolve species_map when not provided |
| `src/qmatsuite/mcp/tools/create_calculation.py` | Modified | Auto-resolve at creation, dynamic hint |
| `src/qmatsuite/mcp/tools/run_calculation.py` | Modified | Reject pseudo engines with empty species_map |
| `src/qmatsuite/mcp/tools/inspect_calculation.py` | Modified | Added resource_status to payload |
| `src/qmatsuite/mcp/server.py` | Modified | Added 2 tool imports (26 total) |
| `tests/mcp/test_stage_p2.py` | Created | 21 new tests |
| `tests/mcp/test_stage11.py` | Modified | 24→26 tool count, new tool names |
| `tests/mcp/test_stage_p1.py` | Modified | Updated hint test + tool count |
| `docs/history/worklogs/MCP_STAGE_P2_WORKLOG.md` | Modified | This file |

---

## Remaining Gaps

1. **VASP auto-resolve**: VASP uses POTCAR variants (Fe vs Fe_pv vs Fe_sv) which
   require a different resolution strategy than QE/ABINIT/Siesta pseudos. Currently
   agents must use `set_species_map` manually for VASP. Community "recommended"
   variant table would enable auto-resolve (see Q2 in review doc).

2. **CP2K/ABINIT/Siesta resource discovery**: Classified as "unmanaged" — these
   engines need pseudopotentials but automated discovery is not yet implemented.
   ABINIT and Siesta are in `PSEUDO_ENGINES` for auto-resolve (they share the
   same pseudo resolution chain as QE), but `list_available_resources` reports
   them as unmanaged for discovery UI.

3. **SSSP library not installed**: Auto-resolve falls back to internal pseudos
   (`resources/pseudo/`). These cover Si, Al, C, H, O, Fe, Cu, Li, He — sufficient
   for dev/demo but not production. Full SSSP Precision install (D4, D7) is a
   separate infrastructure task.

4. **Cutoff propagation**: `PseudoResolutionResult.cutoffs` contains recommended
   ecutwfc/ecutrho per element but auto-resolve currently only sets species_map,
   not cutoffs. A future enhancement could auto-set ecutwfc from cutoff data.
