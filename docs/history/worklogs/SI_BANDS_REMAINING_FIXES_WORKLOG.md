# Si Bands Remaining Fixes: C1 + C2 + C3 + M2 + C4

## Context

After running a real Si band-structure workflow through QMatSuite's MCP interface, five issues were identified that prevent a seamless end-to-end experience. These range from the MCP tool not supporting QE card parameters (C1) to missing filband injection (C2), missing k-path generation tool (C3), broken dry-run preview for non-mesh K_POINTS (M2), and missing knowledge about `nbnd` (C4).

---

## Phase 0: Worklog Setup

Create `docs/history/worklogs/SI_BANDS_REMAINING_FIXES_WORKLOG.md` and update it continuously.

---

## C1: `set_parameters` Cannot Set QE Cards

**File**: `src/qmatsuite/mcp/tools/set_parameters.py`

**Root cause**: Line 53 hardcodes `params={"parameters": params}`, preventing cards.

**Fix**: Add auto-detection logic before the `update_step_params()` call:

```python
_QE_CARD_KEYS = frozenset({
    "K_POINTS", "ATOMIC_SPECIES", "ATOMIC_POSITIONS",
    "CELL_PARAMETERS", "CONSTRAINTS", "OCCUPATIONS", "ATOMIC_FORCES",
})
_QE_NAMELIST_KEYS = frozenset({
    "CONTROL", "SYSTEM", "ELECTRONS", "IONS", "CELL",
})

# Classify top-level keys
params_dict = {}
cards_dict = {}
for key, value in params.items():
    if key == "cards":
        cards_dict.update(value)      # explicit cards namespace
    elif key == "parameters":
        params_dict.update(value)     # explicit parameters namespace
    elif key in _QE_CARD_KEYS:
        cards_dict[key] = value       # auto-route to cards
    else:
        params_dict[key] = value      # default to parameters (covers namelists + non-QE)

patch = {}
if params_dict:
    patch["parameters"] = params_dict
if cards_dict:
    patch["cards"] = cards_dict
if not patch:
    patch = {"parameters": params}    # backward compat: empty → parameters

svc.calculation.update_step_params(
    calc_selector=calc_ulid,
    step_selector=step_ulid,
    params=patch,
)
```

**Key verification**: `service.py:4022-4031` confirms API accepts `{"cards": {...}}` via `apply_patch`. StepDoc YAML has top-level `cards:` key. Only QE uses cards.

**Tests** (in `tests/mcp/test_bands_workflow.py`):
- `test_set_parameters_routes_kpoints_to_cards` — K_POINTS auto-routed
- `test_set_parameters_routes_system_to_parameters` — SYSTEM stays in parameters
- `test_set_parameters_mixed_cards_and_params` — both in one call
- `test_set_parameters_explicit_namespace` — `{"cards": {...}, "parameters": {...}}`
- `test_set_parameters_backward_compatible` — existing ecutwfc/nbnd still works

---

## C3: `generate_kpath` MCP Tool

**New file**: `src/qmatsuite/mcp/tools/generate_kpath.py`

**Existing code to reuse**:
- `analysis/kpath.py:145-248` — `generate_kpath()` function
- `analysis/kpath.py:63-110` — `KPathResult.to_qe_kpoints_crystal_b()` returns `{"option": "crystal_b", "data": [...]}`
- `api/service.py:8375-8398` — `QMSService.generate_kpath()` wrapper
- `core/resolution.require_structure()` + `io/structure_io.read_structure()` — resolve selector to pymatgen Structure

**Implementation**:
```python
@mcp.tool
def generate_kpath(
    structure_selector: str,
    points_per_segment: int = 20,
    path_type: str = "hinuma",
) -> dict:
    svc = get_service()
    # Resolve structure selector → pymatgen Structure
    from qmatsuite.core.resolution import require_structure
    from qmatsuite.io.structure_io import read_structure
    struct_resolved = require_structure(svc.project_root, structure_selector)
    pmg_structure = read_structure(struct_resolved.absolute_path)

    # Generate k-path
    kpath_result = QMSService.generate_kpath(pmg_structure, points_per_segment, path_type)
    kpoints_card = kpath_result.to_qe_kpoints_crystal_b()

    return make_response({
        "lattice_type": kpath_result.lattice_type,
        "spacegroup_symbol": kpath_result.spacegroup_symbol,
        "spacegroup_number": kpath_result.spacegroup_number,
        "path_string": kpath_result.path_string(),
        "path_type": path_type,
        "n_kpoints": len(kpoints_card["data"]),
        "n_segments": len(kpath_result.segments),
        "kpoints_card": kpoints_card,
        "labels": kpath_result.labels,
        "coords": [list(c) for c in kpath_result.coords],
    }, context_hint="Use set_parameters(..., params={'K_POINTS': data['kpoints_card']}) to apply.")
```

**Registration**: Add `import qmatsuite.mcp.tools.generate_kpath` in `server.py` at Stage 2A.

**Tool count**: Update from 29 → 30 in `test_stage11.py:316` and expected_names set.

**Tests**:
- `test_generate_kpath_si_diamond` — returns FCC BZ path
- `test_generate_kpath_returns_qe_card_format` — has `kpoints_card` with option+data
- `test_generate_kpath_invalid_structure` — proper error
- `test_generate_kpath_points_per_segment` — density changes n_kpoints
- `test_generate_kpath_card_usable_with_set_parameters` — integration with C1

---

## C2: Runtime-Managed `filband` Injection

**File**: `src/qmatsuite/calculation/structure_steps.py`

**Root cause**: `_inject_calculation_prefix_outdir()` (line 353) only injects `prefix` and `outdir`. `filband` is not managed, so QE defaults to `bands.out`, producing `bands.out.gnu` — not matching evidence glob `*.bands.dat.gnu`.

**Fix Part A** — Add filband injection to `_inject_calculation_prefix_outdir()`:

After the outdir injection block (~line 459), add:
```python
# Inject filband for BANDS module: {prefix}.bands.dat → output *.bands.dat.gnu
if calculation_prefix and "filband" in param_to_sections:
    filband_sections = param_to_sections["filband"]
    if filband_sections:
        target_section = filband_sections[0]
        namelist = qe_input.get_namelist(target_section)
        if not namelist:
            namelist = QENamelist(name=target_section)
            qe_input.namelists.append(namelist)
        filband_value = f"{calculation_prefix}.bands.dat"
        namelist.parameters["filband"] = filband_value
        logger.info(
            f"[FILBAND_INJECTION] Injected filband '{filband_value}' "
            f"into {target_section}.filband"
        )
```

This produces `{prefix}.bands.dat.gnu` which matches the evidence glob `*.bands.dat.gnu`.

**Fix Part B** — Widen evidence glob (defense-in-depth):

In `drivers/qe/driver.py:21`, change:
```python
evidence_files=["*.bands.dat.gnu"],
```
to:
```python
evidence_files=["*.bands.dat.gnu", "*.bands.out.gnu", "*.gnu"],
```

**Tests**: Unit test that filband param appears in generated input. Integration test with real QE is ideal but may be deferred if too heavy (verify manually or extend existing real-QE tests).

---

## M2: Dry-Run Materializer Card Handling

**Files**:
- `src/qmatsuite/mcp/tools/inspect_calculation.py` — `_merge_cards_into_params()` (line 303)
- `src/qmatsuite/drivers/qe/inputspec.py` — `_write_qe_text_direct()` (line 88)

**Root cause**: Two-part problem:
1. `_merge_cards_into_params()` converts ALL K_POINTS to mesh+shift, losing the option
2. `_write_qe_text_direct()` always writes `K_POINTS (automatic)`

**Fix Part 1** — `_merge_cards_into_params()` in `inspect_calculation.py`:

Replace lines 318-327 with:
```python
if "kpoints" not in params:
    kp = cards.get("K_POINTS", {})
    if kp:
        kp_option = (kp.get("option") or "").lower()
        kpath_formats = {"crystal_b", "crystal_c", "tpiba_b", "tpiba_c"}
        explicit_formats = {"tpiba", "crystal"}
        if kp_option in kpath_formats or kp_option in explicit_formats:
            # Preserve full card structure for k-path/explicit formats
            params["kpoints"] = {
                "option": kp.get("option"),
                "data": kp.get("data", []),
            }
        elif kp_option == "gamma":
            params["kpoints"] = {"option": "gamma"}
        else:
            # automatic or unspecified: extract mesh+shift
            data = kp.get("data", [[4, 4, 4, 0, 0, 0]])
            row = data[0] if data else [4, 4, 4, 0, 0, 0]
            params["kpoints"] = {
                "mesh": list(row[:3]),
                "shift": list(row[3:6]) if len(row) >= 6 else [0, 0, 0],
            }
```

**Fix Part 2** — `_write_qe_text_direct()` in `inputspec.py`:

Replace lines 135-140 with:
```python
kpoints = params.get("kpoints", {})
if kpoints:
    kp_option = kpoints.get("option", "").lower() if isinstance(kpoints.get("option"), str) else ""
    kp_data = kpoints.get("data", [])

    if kp_option == "gamma":
        lines.append("K_POINTS {gamma}")
    elif kp_option in ("crystal_b", "crystal_c", "tpiba_b", "tpiba_c") and kp_data:
        lines.append(f"K_POINTS {{{kp_option}}}")
        lines.append(f"  {len(kp_data)}")
        for row in kp_data:
            if isinstance(row, (list, tuple)) and len(row) >= 4:
                lines.append(f"  {row[0]:.10f}  {row[1]:.10f}  {row[2]:.10f}  {int(row[3])}")
            elif isinstance(row, (list, tuple)) and len(row) >= 3:
                lines.append(f"  {row[0]:.10f}  {row[1]:.10f}  {row[2]:.10f}")
    elif kp_option in ("tpiba", "crystal") and kp_data:
        lines.append(f"K_POINTS {{{kp_option}}}")
        lines.append(f"  {len(kp_data)}")
        for row in kp_data:
            if isinstance(row, (list, tuple)) and len(row) >= 4:
                lines.append(f"  {row[0]:.10f}  {row[1]:.10f}  {row[2]:.10f}  {row[3]:.10f}")
    else:
        # automatic (default)
        mesh = kpoints.get("mesh", kpoints.get("grid", [4, 4, 4]))
        shift = kpoints.get("shift", [0, 0, 0])
        lines.append("K_POINTS (automatic)")
        lines.append(f"  {mesh[0]} {mesh[1]} {mesh[2]}  {shift[0]} {shift[1]} {shift[2]}")
```

**Tests**:
- `test_dry_run_kpoints_tpiba_b` — K_POINTS {tpiba_b} with data rows
- `test_dry_run_kpoints_automatic` — no regression
- `test_dry_run_kpoints_gamma` — gamma format
- `test_dry_run_kpoints_crystal_b` — crystal_b (from generate_kpath)

---

## C4: `nbnd` Knowledge Base Entry

**File**: `src/qmatsuite/mcp/knowledge/builtin_entries.py`

**Fix**: Append to `BUILTIN_ENTRIES` list:
```python
{
    "grade": "finding",
    "scope_engine": "qe",
    "scope_workflow": "bands",
    "scope_system_type": "*",
    "scope_method": "dft",
    "content": (
        "For band structure calculations, QE default nbnd = n_electrons/2 "
        "only includes occupied (valence) bands. To see the band gap and "
        "conduction bands, set nbnd to at least 2 * (n_electrons/2). "
        "A practical default: nbnd = n_electrons/2 + max(4, n_electrons/4). "
        "Set via: set_parameters(calc_ulid=..., step=<bandspw_step>, "
        "params={'SYSTEM': {'nbnd': <value>}})"
    ),
    "confidence": "high",
    "source_type": "builtin",
    "source_origin": "QE documentation",
    "created_by": "qmatsuite-builtin",
    "tags": '["nbnd", "bands", "band_structure", "conduction_bands"]',
},
```

Also add a `VASP NBANDS` variant:
```python
{
    "grade": "finding",
    "scope_engine": "vasp",
    "scope_workflow": "bands",
    "scope_system_type": "*",
    "scope_method": "dft",
    "content": (
        "For VASP band structure calculations, the default NBANDS may not "
        "include enough empty bands to see conduction bands clearly. "
        "Set NBANDS to at least 2 * N_occupied for a useful band structure. "
        "Set via: set_parameters(calc_ulid=..., params={'INCAR': {'NBANDS': <value>}})"
    ),
    "confidence": "high",
    "source_type": "builtin",
    "source_origin": "VASP documentation",
    "created_by": "qmatsuite-builtin",
    "tags": '["nbands", "bands", "band_structure", "conduction_bands"]',
},
```

**Tests**:
- `test_search_knowledge_nbnd` — `search_knowledge(query="nbnd band structure")` finds entry
- `test_search_knowledge_conduction_bands` — `search_knowledge(query="conduction bands")` finds it

Note: The builtin DB must be rebuilt after adding entries. Delete `~/.qmatsuite/knowledge/builtin.db` or the test fixture will handle it.

---

## Files Summary

### New Files
- `src/qmatsuite/mcp/tools/generate_kpath.py` — C3
- `tests/mcp/test_bands_workflow.py` — all tests for C1/C2/C3/M2/C4
- `docs/history/worklogs/SI_BANDS_REMAINING_FIXES_WORKLOG.md` — mandatory worklog

### Modified Files
- `src/qmatsuite/mcp/tools/set_parameters.py` — C1: cards auto-routing
- `src/qmatsuite/calculation/structure_steps.py` — C2: filband injection
- `src/qmatsuite/drivers/qe/driver.py` — C2: widen evidence glob
- `src/qmatsuite/drivers/qe/inputspec.py` — M2: K_POINTS format handling
- `src/qmatsuite/mcp/tools/inspect_calculation.py` — M2: card merge fix
- `src/qmatsuite/mcp/knowledge/builtin_entries.py` — C4: nbnd entry
- `src/qmatsuite/mcp/server.py` — register generate_kpath
- `tests/mcp/test_stage11.py` — tool count 29→30

---

## Execution Order

1. **Phase 0**: Create worklog
2. **Phase 1**: Write ALL failing tests first, confirm failures
3. **Phase 2**: Implement C1 (set_parameters cards routing)
4. **Phase 3**: Implement C3 (generate_kpath tool)
5. **Phase 4**: Implement C2 (filband injection + evidence glob)
6. **Phase 5**: Implement M2 (dry-run card handling)
7. **Phase 6**: Implement C4 (knowledge entry)
8. **Phase 7**: Integration test — full bands workflow
9. **Phase 8**: Full regression — `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

---

## Verification

1. Run `test_bands_workflow.py` — all new tests pass
2. Run `test_stage11.py` — tool count updated, all pass
3. Run `test_stage2.py` — set_parameters backward compat preserved
4. Run full suite — zero regressions

---

## Work Progress

### Phase 0: Worklog Setup — DONE
- Created this worklog file.

### Phase 2: C1 — set_parameters cards routing — DONE
- Added `_QE_CARD_KEYS` frozenset to auto-detect QE card keys
- Top-level keys classified: `cards`/`parameters` explicit namespaces, QE card keys auto-routed, everything else to parameters
- Backward compatible: existing `{"SYSTEM": {"ecutwfc": 60}}` still works
- 5 new tests: routing, mixed, explicit namespace, backward compat

### Phase 3: C3 — generate_kpath MCP tool — DONE
- New file: `src/qmatsuite/mcp/tools/generate_kpath.py`
- Wraps existing `analysis/kpath.py:generate_kpath()` + `KPathResult.to_qe_kpoints_crystal_b()`
- Returns lattice_type, spacegroup, path_string, kpoints_card (crystal_b format), labels, coords
- Registered in server.py at Stage 2A
- Tool count: 29 → 30 (updated test_stage11.py, test_stage_p1.py, test_stage_p2.py)
- 5 new tests: Si diamond kpath, QE card format, invalid structure, points_per_segment, integration with set_parameters

### Phase 4: C2 — filband injection + evidence glob — DONE
- Added conditional filband injection to `_inject_calculation_prefix_outdir()` in structure_steps.py
- Injection is conditional: only injects if user hasn't already set filband (unlike prefix/outdir which always override per R3)
- filband value: `{calculation_prefix}.bands.dat` → produces `*.bands.dat.gnu` matching evidence glob
- Widened evidence glob in driver.py: added `*.bands.out.gnu` and `*.gnu` as fallbacks
- 2 new tests: filband in schema, evidence glob widened

### Phase 5: M2 — dry-run card handling — DONE
- Fixed `_merge_cards_into_params()` in inspect_calculation.py:
  - crystal_b/crystal_c/tpiba_b/tpiba_c: preserve full card structure (option + data)
  - gamma: preserve as `{"option": "gamma"}`
  - automatic/unspecified: extract mesh+shift (existing behavior)
- Fixed `_write_qe_text_direct()` in inputspec.py:
  - Handles gamma, crystal_b/c, tpiba_b/c, tpiba, crystal, and automatic formats
  - No regression for automatic format
- 7 new tests: crystal_b merge, gamma merge, automatic merge, crystal_b write, gamma write, automatic write, tpiba_b write

### Phase 6: C4 — nbnd knowledge entries — DONE
- Added QE nbnd entry (scope_engine="qe", scope_workflow="bands")
- Added VASP NBANDS entry (scope_engine="vasp", scope_workflow="bands")
- 4 new tests: entry existence, search knowledge

### Phase 8: Full Regression — DONE
- 6208 passed, 0 failed, 4 skipped
- 23 new tests in test_bands_workflow.py all passing
- No regressions in existing tests
- Pre-existing CLI test (test_si_bands_manual_calculation_cli) initially regressed due to unconditional filband override → fixed with conditional injection

