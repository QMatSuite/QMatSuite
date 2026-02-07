MA# GUI Multi-Engine + Demo System: Implementation Plan

**Status**: PLAN (awaiting execution)
**Authority**: `docs/architecture/GUI_ENGINE_FAMILY_DEMO_SPEC.md` v1.1
**Date**: 2026-02-07

---

## Executive Summary

9 milestones (M0-M8) transforming QMatSuite from QE-only GUI to engine-agnostic GUI.
Each milestone is self-contained, test-verifiable, and produces a green test suite.

### Stop & Opus Audit Points

| Milestone | Why |
|-----------|-----|
| **M0** (gates + driver protocol) | Foundation for everything. Wrong gates = cascading failures. |
| **M3** (companion routing) | Architectural change to materialization. Must verify before RPCs. |
| **M5** (first GUI milestone) | Backend→GUI boundary. Must verify RPC contracts before GUI work. |
| **M8** (final cleanup) | Deletion milestone. Must verify nothing breaks. |

---

## Preflight Inventory

### A. Silent QE Fallbacks (10 locations)

| # | File | Line | Pattern | Fix |
|---|------|------|---------|-----|
| F1 | `src/quantumvitas/api/service.py` | 3182 | `engine = step_spec.engine if step_spec else "qe"` | Hard error if step_spec is None |
| F2 | `src/quantumvitas/api/service.py` | 3825 | `engine_family = getattr(calc_model, 'engine_family', None) or "qe"` | Raise if engine_family is None for base step |
| F3 | `src/quantumvitas/api/service.py` | 3921 | `engine = step_spec.engine if step_spec else "qe"` | Hard error if step_spec is None |
| F4 | `src/quantumvitas/api/service.py` | 6244 | `engine_family = "pyscf" if structure_kind == "molecule" else "qe"` | Accept null (UNDECIDED) |
| F5 | `src/quantumvitas/api/service.py` | 7267 | `def resolve_step_type_spec(..., engine_family: str = "qe")` | Remove default; require caller to pass |
| F6 | `src/quantumvitas/core/models.py` | 359 | `engine_family = "qe"` (final default) | Allow null; raise on base-step-add |
| F7 | `src/quantumvitas/core/templates.py` | 399 | `calculation_data["engine_family"] = "qe"` | Require engine_family from caller |
| F8 | `src/quantumvitas/frontends/cli/app.py` | 848 | `engine_family = "qe"` | Accept null; prompt user |
| F9 | `src/quantumvitas/cli/main.py` | 1289 | `engine_family = "qe"` | Use calc_data value; raise if missing for base step |
| F10 | `src/quantumvitas/workflow/templates.py` | 486 | `engine_family = "qe"` | Raise if engine_family is None |

### B. QE-Specific GUI Code (must be generalized)

| # | File | Lines | What |
|---|------|-------|------|
| G1 | `gui/src/components/panels/StepDetailPanel.tsx` | 52-73 | `stepTypeToModule()` — QE module mapping |
| G2 | `gui/src/components/panels/StepDetailPanel.tsx` | 76-121 | `LEGACY_EDITABLE_PARAMS` — QE parameter defs |
| G3 | `gui/src/components/panels/CalculationOverviewTab.tsx` | 453-461 | Hard-coded QE step dropdown (7 types) |
| G4 | `gui/src/components/panels/CalculationListPanel.tsx` | 1345-1354 | Hard-coded QE step dropdown (10 types) |
| G5 | `gui/src/components/panels/QEParameterBrowserPanel.tsx` | entire | QE-only parameter browser (1400+ lines) |
| G6 | `gui/src/hooks/useQEParameterMetadata.ts` | entire | QE-only metadata hook (370 lines) |
| G7 | `gui/src/hooks/useQVClient.ts` | 54, 55-58 | `listQeUiParameters`, `listQeParameterMetadata` |
| G8 | `gui/src/types/qv.ts` | 397-405, 493-496 | `QEDetectionResult`, QE RPC types |
| G9 | `gui/src/components/panels/SettingsPanel.tsx` | 300-349 | Hard-coded "Quantum ESPRESSO" section |
| G10 | `gui/src/components/dialogs/CreateCalculationDialog.tsx` | 96-101 | No engine_family in create_calculation payload |

### C. QE-Specific Daemon RPC Handlers (9 handlers)

| # | Handler | server.py Line | RPC Name |
|---|---------|---------------|----------|
| H1 | `_handle_detect_qe` | 718 | `detect_qe` |
| H2 | `_handle_list_qe_engines` | 738 | `list_qe_engines` |
| H3 | `_handle_discover_qe_engines` | 748 | `discover_qe_engines` |
| H4 | `_handle_set_qe_engine` | 758 | `set_qe_engine` |
| H5 | `_handle_list_qe_ui_parameters` | 1432 | `list_qe_ui_parameters` |
| H6 | `_handle_list_qe_parameter_metadata` | 1493 | `list_qe_parameter_metadata` |
| H7 | `_handle_reload_qe_parameter_metadata` | 1911 | `reload_qe_parameter_metadata` |
| H8 | `_handle_get_qe_parameter_metadata_debug_info` | 1959 | `get_qe_parameter_metadata_debug_info` |
| H9 | `_handle_import_step_from_qe_input` | 4157 | `import_step_from_qe_input` |

### D. Demo Schema Violations (20 snapshots)

| # | File | engine_family | step_type_spec Issues |
|---|------|--------------|----------------------|
| D1 | `water_orca_scf.yml` | `orca` (explicit) | `qe_scf` (wrong prefix) |
| D2 | `methane_orca_freq.yml` | `orca` (explicit) | `qe_scf` (wrong prefix) |
| D3 | `formaldehyde_orca_tddft.yml` | `orca` (explicit) | `qe_scf` + `pyscf_td` (wrong prefixes) |
| D4-D16 | 13 QE demos | missing | Prefixes correct (qe_*) |
| D17-D19 | 3 W90 demos | missing | Mixed qe_* + w90_* (correct for companion) |
| D20 | `water_pyscf_scf.yml` | missing | pyscf_scf (correct) |

### E. Pre-existing Issues (NOT addressed by this plan)

- `qe_vc-relax` appears in demos `03_Si_vc_relax.yml`, `06_Al_DOS.yml`, `13_graphene.yml`. The gen step `vc-relax` is not in GenStepRegistry.GEN_STEPS. This is a pre-existing constitutional violation (VC is a parameter per STEP_TYPE_GEN_SPEC_CONSTITUTION.md S8). Fixing this is a separate task.
- `qe_gipaw` in `12_NMR_gipaw.yml` — `gipaw` is not in GenStepRegistry. Same category.

---

## Milestone Sequence

### M0: Driver Protocol + Gate Tests (Foundation)

**Goal**: Add `ENGINE_ROLE` and `COMPANION_ENGINES` to all 15 drivers. Write gate tests for EF6, EF8, EF9.

**Files to change**:
- `src/quantumvitas/core/driver_protocol.py` (add 2 class attributes to BaseEngineDriver)
- `src/quantumvitas/drivers/qe/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/vasp/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/abinit/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/cp2k/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/siesta/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/gpaw/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/orca/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/gaussian/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/psi4/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/pyscf/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/xtb/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/lammps/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/w90/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/qmcpack/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- `src/quantumvitas/drivers/yambo/driver.py` (add ENGINE_ROLE + COMPANION_ENGINES)
- **NEW** `tests/gates/test_postproc_gen_uniqueness.py`
- **NEW** `tests/gates/test_companion_completeness.py`
- **NEW** `tests/gates/test_demo_integrity.py`

**Files NOT to touch**: service.py, server.py, GUI files, workflow/ files

**What to add to BaseEngineDriver** (`driver_protocol.py:161`):
```python
ENGINE_ROLE: str = "base"  # "base" or "postprocessing"
COMPANION_ENGINES: frozenset = frozenset()  # only meaningful for base engines
```

**What to add to each driver** (after SUPPORTED_GEN_STEPS):
- 12 base engines: `ENGINE_ROLE = "base"`, `COMPANION_ENGINES = frozenset()` (except QE)
- QE: `ENGINE_ROLE = "base"`, `COMPANION_ENGINES = frozenset({"w90", "qmcpack", "yambo"})`
- 3 postproc engines: `ENGINE_ROLE = "postprocessing"`, `COMPANION_ENGINES = frozenset()`

**Acceptance criteria**:
- [ ] `python -m pytest tests/gates/test_postproc_gen_uniqueness.py -v` passes
- [ ] `python -m pytest tests/gates/test_companion_completeness.py -v` passes
- [ ] `python -m pytest tests/gates/test_demo_integrity.py -v` passes (or xfails for known ORCA bugs)
- [ ] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all existing tests still pass
- [ ] `grep -rn "ENGINE_ROLE" src/quantumvitas/drivers/*/driver.py | wc -l` = 15
- [ ] `grep -rn "COMPANION_ENGINES" src/quantumvitas/drivers/*/driver.py | wc -l` = 15

**Expected failure modes**:
1. Putting ENGINE_ROLE on the protocol (abstract class) instead of BaseEngineDriver (concrete class)
2. Forgetting to add to one of the 15 drivers
3. Making COMPANION_ENGINES a set instead of frozenset (mutable class attribute)

**Stop & Opus Audit**: YES. Verify gate test logic before proceeding.

---

### M1: Fix Demo Snapshots

**Goal**: All 20 demos pass the demo integrity gate. Every demo has explicit `engine_family` and correct `step_type_spec` prefixes.

**Files to change**:
- `resources/demo_projects/water_orca_scf.yml` (fix step_type_spec + add engine_family)
- `resources/demo_projects/methane_orca_freq.yml` (fix step_type_spec + add engine_family)
- `resources/demo_projects/formaldehyde_orca_tddft.yml` (fix step_type_spec + add engine_family)
- `resources/demo_projects/00_Si_scf.yml` (add engine_family: qe)
- `resources/demo_projects/03_Si_vc_relax.yml` (add engine_family: qe)
- `resources/demo_projects/04_Si_DOS.yml` (add engine_family: qe)
- `resources/demo_projects/06_Al_DOS.yml` (add engine_family: qe)
- `resources/demo_projects/07_Si_bandStructure.yml` (add engine_family: qe)
- `resources/demo_projects/08_Fe_DOS.yml` (add engine_family: qe)
- `resources/demo_projects/09_Si_phonon.yml` (add engine_family: qe)
- `resources/demo_projects/12_NMR_gipaw.yml` (add engine_family: qe)
- `resources/demo_projects/13_graphene.yml` (add engine_family: qe)
- `resources/demo_projects/15_bulk_modulus_Si.yml` (add engine_family: qe)
- `resources/demo_projects/19_Si_CPMD.yml` (add engine_family: qe)
- `resources/demo_projects/si_bands_demo.yml` (add engine_family: qe)
- `resources/demo_projects/si_dos_demo.yml` (add engine_family: qe)
- `resources/demo_projects/copper_wannier90_demo.yml` (add engine_family: qe)
- `resources/demo_projects/diamond_wannier90_demo.yml` (add engine_family: qe)
- `resources/demo_projects/silicon_wannier90_demo.yml` (add engine_family: qe)
- `resources/demo_projects/water_pyscf_scf.yml` (add engine_family: pyscf)

**Files NOT to touch**: Python source files, GUI files

**Exact changes for ORCA demos**:
- `water_orca_scf.yml`: Change `step_type_spec: qe_scf` to `step_type_spec: orca_scf`
- `methane_orca_freq.yml`: Change `step_type_spec: qe_scf` to `step_type_spec: orca_scf`
- `formaldehyde_orca_tddft.yml`: Change `step_type_spec: qe_scf` to `step_type_spec: orca_scf`, change `step_type_spec: pyscf_td` to `step_type_spec: orca_td`

**Exact changes for ALL demos**: Add `engine_family: <engine>` at the calculation level, as a sibling of `mode:` and `working_dir:`. For W90 demos, set `engine_family: qe` (base family is QE; w90 steps are companions).

**Acceptance criteria**:
- [ ] `python -m pytest tests/gates/test_demo_integrity.py -v` passes (no xfails)
- [ ] `grep -c "engine_family:" resources/demo_projects/*.yml` = 20
- [ ] `grep "engine_family:" resources/demo_projects/water_orca_scf.yml` shows `orca`
- [ ] `grep "step_type_spec:" resources/demo_projects/water_orca_scf.yml` shows `orca_scf`
- [ ] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all pass

**Expected failure modes**:
1. Adding engine_family at the wrong YAML nesting level (must be under `calculations[0]`, not under `project`)
2. Using `engine_family: w90` for W90 demos (wrong — base family is qe)
3. Not changing `pyscf_td` to `orca_td` in formaldehyde demo

**Stop & Opus Audit**: NO (straightforward data fix).

---

### M2: Remove Silent QE Fallbacks

**Goal**: Zero `or "qe"` fallbacks in non-driver code. UNDECIDED (`engine_family: null`) is legal.

**Files to change**:
- `src/quantumvitas/api/service.py` (lines 3182, 3825, 3921, 6244, 7267)
- `src/quantumvitas/core/models.py` (line 359)
- `src/quantumvitas/core/templates.py` (line 399)
- `src/quantumvitas/frontends/cli/app.py` (line 848)
- `src/quantumvitas/cli/main.py` (lines 1289, 1291)
- `src/quantumvitas/workflow/templates.py` (line 486)
- **NEW** `tests/gates/test_no_qe_fallback.py`

**Files NOT to touch**: drivers/, GUI files, daemon/server.py

**Replacement strategy for each fallback**:

**F1 (service.py:3182)**: Replace `step_spec.engine if step_spec else "qe"` with:
```python
if step_spec is None:
    raise ValueError(f"Unknown step type spec '{step_type_spec}': not registered in StepTypeRegistry")
engine = step_spec.engine
```

**F2 (service.py:3825)**: Replace `getattr(calc_model, 'engine_family', None) or "qe"` with:
```python
engine_family = getattr(calc_model, 'engine_family', None)
if engine_family is None:
    raise ValueError("Cannot add base step to UNDECIDED calculation without engine_family. Set engine_family first.")
```

**F3 (service.py:3921)**: Same pattern as F1.

**F4 (service.py:6244)**: Replace conditional default with allowing null:
```python
# engine_family is now passed by caller. None = UNDECIDED (legal).
# Do NOT default to "qe" or "pyscf".
```

**F5 (service.py:7267)**: Remove default value from parameter:
```python
def resolve_step_type_spec(step_type_gen: str, engine_family: str) -> str:
```
All callers must pass engine_family explicitly.

**F6 (models.py:359)**: Allow null engine_family:
```python
# engine_family may be None (UNDECIDED state is legal per EF1)
```

**F7 (templates.py:399)**: Require caller to provide engine_family:
```python
if "engine_family" not in calculation_data or calculation_data["engine_family"] is None:
    raise ValueError("engine_family is required for template instantiation")
```

**F8 (cli/app.py:848)**: Accept null; prompt user or require --engine flag.

**F9-F10 (cli/main.py, workflow/templates.py)**: Similar pattern — require explicit value, raise if missing.

**Gate test** (`test_no_qe_fallback.py`): Scan all Python files in `src/quantumvitas/` (excluding `drivers/`) for patterns:
- `or "qe"`
- `else "qe"`
- `= "qe"` as a default parameter value
- `engine_family: str = "qe"`
Allowlist: zero entries.

**Acceptance criteria**:
- [ ] `python -m pytest tests/gates/test_no_qe_fallback.py -v` passes
- [ ] `grep -rn 'or "qe"' src/quantumvitas/ --include="*.py" | grep -v drivers/ | grep -v tests/` = empty
- [ ] `grep -rn 'else "qe"' src/quantumvitas/ --include="*.py" | grep -v drivers/ | grep -v tests/` = empty
- [ ] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all pass

**Expected failure modes**:
1. Removing a default but not updating all callers → test failures
2. Making engine_family required everywhere, breaking UNDECIDED creation path
3. Leaving one fallback in an obscure method

**Stop & Opus Audit**: NO (verify via gate test).

---

### M3: Companion Allowlist Routing

**Goal**: Materialization uses companion allowlist. StepTypeRegistry first-match is eliminated for cross-engine step resolution.

**Files to change**:
- `src/quantumvitas/workflow/generalized_steps.py` (rewrite `materialize_public_step_key`, `materialize_workflow`)
- `src/quantumvitas/core/driver_registry.py` (add `get_postproc_engine_for_gen_step()`)
- **NEW** `tests/gates/test_engine_family_lifecycle.py`
- **NEW** `tests/gates/test_decided_companion_validation.py`
- Tests in `tests/workflow/` for updated materialization

**Files NOT to touch**: drivers/ (already done in M0), GUI files, daemon/server.py

**Key changes to generalized_steps.py**:

`materialize_public_step_key(public_step_key, engine_family)`:
- If engine_family is not None (DECIDED):
  - Try `DriverRegistry.materialize_step_type(engine_family, gen)` first
  - If fails, iterate `driver.COMPANION_ENGINES` and try each
  - If no match, raise `UnsupportedStepError`
  - **DELETE** the StepTypeRegistry.get() first-match path
- If engine_family is None (UNDECIDED):
  - Scan all postprocessing engines for the gen step
  - If exactly 1 match → return materialized spec
  - If 0 matches → raise `BaseStepRequiresFamilyError`
  - If >1 match → raise `AmbiguousPostprocError` (should not happen per EF8)

`materialize_workflow(generalized_steps, engine_family)`:
- If engine_family is None, raise ValueError (workflows require DECIDED)

**Acceptance criteria**:
- [ ] `python -m pytest tests/gates/test_engine_family_lifecycle.py -v` passes
- [ ] `python -m pytest tests/gates/test_decided_companion_validation.py -v` passes
- [ ] `materialize_public_step_key("wannierprep", "qe")` returns `"w90_wannierprep"`
- [ ] `materialize_public_step_key("scf", None)` raises `BaseStepRequiresFamilyError`
- [ ] `materialize_public_step_key("vmc", None)` returns `"qmcpack_vmc"`
- [ ] `materialize_public_step_key("wannierprep", "vasp")` raises `UnsupportedStepError`
- [ ] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all pass
- [ ] `grep -n "StepTypeRegistry" src/quantumvitas/workflow/generalized_steps.py` returns NO first-match usage

**Expected failure modes**:
1. Breaking `materialize_workflow` for QE workflows (the primary path)
2. Not handling 0-mappings correctly (some gen steps are explicitly unsupported)
3. Importing driver modules in generalized_steps.py (breaks kernel isolation)

**Stop & Opus Audit**: YES. Verify materialization logic is correct before building RPCs on top.

---

### M4: Generic Backend RPCs

**Goal**: New engine-agnostic RPCs exist. QE-specific RPCs still work (deprecated but not removed).

**Files to change**:
- `src/quantumvitas/daemon/server.py` (add new RPC handlers)
- `src/quantumvitas/api/service.py` (add new service methods)
- `src/quantumvitas/core/driver_protocol.py` (add `get_managed_keys()` to BaseEngineDriver)
- Tests for new RPCs

**New RPC handlers in server.py**:

| RPC Name | Handler | Returns |
|----------|---------|---------|
| `list_engine_families` | `_handle_list_engine_families` | `[{engine_family, display_name, engine_role, companion_engines, supported_gen_steps}]` |
| `list_step_palette` | `_handle_list_step_palette` | `{base_steps: [...], companion_steps: {engine: [...]}, postproc_steps: [...]}` |
| `list_engine_ui_parameters` | `_handle_list_engine_ui_parameters` | `[{key, label, type, default, description, section, is_managed, managed_reason}]` |
| `list_engine_parameter_metadata` | `_handle_list_engine_parameter_metadata` | Same shape as existing QE metadata RPCs but dispatches on engine_family |
| `set_engine_family` | `_handle_set_engine_family` | Sets engine_family on a calculation (UNDECIDED->DECIDED transition) |

**Files NOT to touch**: GUI files, drivers/ (M0 already done)

**Acceptance criteria**:
- [ ] `list_engine_families` returns 15 engines with correct roles
- [ ] `list_step_palette("qe")` returns scf, nscf, relax, etc. + w90/qmcpack/yambo companions
- [ ] `list_step_palette("vasp")` returns scf, nscf, relax, md, bandspw — no companions
- [ ] `list_step_palette(null)` returns only postproc steps
- [ ] `list_engine_ui_parameters("vasp", "scf")` returns VASP parameter metadata
- [ ] `list_engine_ui_parameters("orca", "scf")` returns ORCA parameter metadata
- [ ] `set_engine_family(calc_path, "qe")` transitions UNDECIDED -> DECIDED
- [ ] Existing QE RPCs (`list_qe_ui_parameters`, etc.) still work (not removed yet)
- [ ] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all pass

**Expected failure modes**:
1. Not dispatching to the correct engine metadata module
2. Returning different shapes from different engines (inconsistent RPC contract)
3. Breaking existing QE RPCs by accidentally modifying shared code

**Stop & Opus Audit**: YES. Verify RPC contracts before GUI starts consuming them.

---

### M5: GUI Step Palette

**Goal**: Step dropdowns are backend-driven, not hard-coded QE lists.

**Files to change**:
- `gui/src/components/panels/CalculationOverviewTab.tsx` (replace hard-coded dropdown at lines 453-461)
- `gui/src/components/panels/CalculationListPanel.tsx` (replace hard-coded dropdown at lines 1345-1354)
- `gui/src/components/dialogs/CreateCalculationDialog.tsx` (add engine_family selector)
- `gui/src/hooks/useQVClient.ts` (add new RPC client methods)
- `gui/src/types/qv.ts` (add new RPC type definitions)

**Files NOT to touch**: StepDetailPanel.tsx (M6), QEParameterBrowserPanel.tsx (M7), SettingsPanel.tsx (M7), Python backend (already done)

**Changes**:

1. **CreateCalculationDialog.tsx**: Add engine_family dropdown populated from `list_engine_families` RPC. Pass `engine_family` in `create_calculation` payload. Add "Decide later" option that sends `engine_family: null`.

2. **CalculationOverviewTab.tsx:453-461**: Replace static `<option>` elements with dynamic list from `list_step_palette(engine_family)` RPC. The engine_family comes from the calculation's data (loaded from calculation.yaml).

3. **CalculationListPanel.tsx:1345-1354**: Same replacement. Remove hard-coded QE step labels like `"SCF (pw.x)"`.

4. **useQVClient.ts**: Add methods:
   - `listEngineFamilies()` → calls `list_engine_families`
   - `listStepPalette(engineFamily)` → calls `list_step_palette`

5. **types/qv.ts**: Add interfaces for `EngineFamilyInfo`, `StepPaletteResult`.

**Acceptance criteria**:
- [ ] Step dropdown in CalculationOverviewTab shows different options for QE vs VASP calculations
- [ ] `grep -c "qe_scf\|qe_nscf\|qe_relax\|qe_bands" gui/src/components/panels/CalculationOverviewTab.tsx` = 0
- [ ] `grep -c "qe_scf\|qe_nscf\|qe_relax\|qe_bands" gui/src/components/panels/CalculationListPanel.tsx` = 0
- [ ] CreateCalculationDialog has engine selector
- [ ] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all pass

**Expected failure modes**:
1. Using step_type_gen values with underscores (e.g., `"vc-relax"` or `"bands_pw"`) in the new RPC payloads
2. Not handling UNDECIDED state in the palette (should show only postproc steps)
3. Breaking the calculation creation flow by requiring engine_family when UNDECIDED is legal

**Stop & Opus Audit**: NO (verify via functional testing).

---

### M6: GUI Parameter Editor

**Goal**: StepDetailPanel uses generic `list_engine_ui_parameters` RPC instead of QE-specific code.

**Files to change**:
- `gui/src/components/panels/StepDetailPanel.tsx` (remove stepTypeToModule, LEGACY_EDITABLE_PARAMS; use generic RPC)
- `gui/src/hooks/useQVClient.ts` (add `listEngineUiParameters`)
- `gui/src/types/qv.ts` (add parameter types)

**Files NOT to touch**: QEParameterBrowserPanel.tsx (M7), SettingsPanel.tsx (M7), Python backend (already done)

**Changes**:

1. **Delete** `stepTypeToModule()` function (lines 52-73)
2. **Delete** `LEGACY_EDITABLE_PARAMS` constant (lines 76-121)
3. **Replace** parameter loading logic: Instead of calling `listQeUiParameters(module, stepType)`, call `listEngineUiParameters(engine_family, step_type_gen)`. The `engine_family` comes from the calculation data.
4. **Managed keys**: Instead of hard-coded CONTROL.prefix check, use `is_managed` flag from RPC response.
5. **K_POINTS card**: The K_POINTS card rendering stays but becomes conditional on engine_family (only QE has K_POINTS). This is already partially abstracted via `get_common_cards` RPC.

**Acceptance criteria**:
- [ ] `grep -c "stepTypeToModule" gui/src/components/panels/StepDetailPanel.tsx` = 0
- [ ] `grep -c "LEGACY_EDITABLE_PARAMS" gui/src/components/panels/StepDetailPanel.tsx` = 0
- [ ] Parameter editing works for QE steps (regression test)
- [ ] Parameter editing shows guided params for VASP steps (if VASP demo exists)
- [ ] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all pass

**Expected failure modes**:
1. Breaking QE parameter display by removing module-based grouping without replacing it
2. Not handling the case where an engine returns empty UI parameters (should fall through to raw editor)
3. Hardcoding the K_POINTS card check to engine_family == "qe" (should use a card abstraction)

**Stop & Opus Audit**: NO (verify via functional testing).

---

### M7: GUI Parameter Browser + Settings

**Goal**: QEParameterBrowserPanel becomes EngineParameterBrowserPanel. Settings panel shows all engines.

**Files to change**:
- `gui/src/components/panels/QEParameterBrowserPanel.tsx` → rename to `EngineParameterBrowserPanel.tsx`
- `gui/src/hooks/useQEParameterMetadata.ts` → rename to `useEngineParameterMetadata.ts`
- `gui/src/components/panels/SettingsPanel.tsx` (generalize QE section)
- `gui/src/hooks/useQVClient.ts` (add `listEngineParameterMetadata`)
- `gui/src/types/qv.ts` (update types)
- Any file that imports `QEParameterBrowserPanel` or `useQEParameterMetadata`

**Files NOT to touch**: Python backend (already done)

**Changes**:

1. **Rename** `QEParameterBrowserPanel.tsx` → `EngineParameterBrowserPanel.tsx`. Add engine_family prop. Replace all `list_qe_parameter_metadata` calls with `list_engine_parameter_metadata(engine_family, ...)`.

2. **Rename** `useQEParameterMetadata.ts` → `useEngineParameterMetadata.ts`. Accept `engine_family` parameter. Replace RPC calls.

3. **SettingsPanel.tsx**: Replace hard-coded "Quantum ESPRESSO" section with a loop over engines from `list_engine_families`. Each engine shows detection status and configuration. For QE, call `detect_qe` (still available). For others, show "configure binary path" form.

**Acceptance criteria**:
- [ ] `ls gui/src/components/panels/QEParameterBrowserPanel.tsx` fails (file deleted)
- [ ] `ls gui/src/components/panels/EngineParameterBrowserPanel.tsx` succeeds (file exists)
- [ ] `ls gui/src/hooks/useQEParameterMetadata.ts` fails (file deleted)
- [ ] `grep -r "QEParameterBrowser" gui/src/` = 0 (no references to old name)
- [ ] `grep -r "useQEParameterMetadata" gui/src/` = 0 (no references to old name)
- [ ] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all pass

**Expected failure modes**:
1. Missing import updates — some file still imports the old name
2. Breaking the parameter browser for QE by changing the RPC without updating the response shape
3. Not handling engines that have no metadata (should show "no metadata available")

**Stop & Opus Audit**: NO (functional testing).

---

### M8: Cleanup — Delete QE-Only Code

**Goal**: Delete all deprecated QE-specific RPC handlers, types, and components. No QE literal defaults remain.

**Files to change**:
- `src/quantumvitas/daemon/server.py` (delete handlers H1-H9 and their registrations)
- `gui/src/hooks/useQVClient.ts` (delete `listQeUiParameters`, `listQeParameterMetadata`)
- `gui/src/types/qv.ts` (delete `QEDetectionResult`, QE RPC types)
- `gui/src/components/panels/SettingsPanel.tsx` (remove any remaining QE-specific code)
- **NEW** `tests/gates/test_no_qe_special_case.py`

**Files NOT to touch**: drivers/qe/ (QE driver is still valid; QE is just one engine)

**Gate test** (`test_no_qe_special_case.py`): Scan for:
- `"detect_qe"` in gui/src/ TypeScript files (should be 0)
- `"list_qe_"` in gui/src/ TypeScript files (should be 0)
- `"_handle_detect_qe"` in daemon/server.py (should be 0)
- `"_handle_list_qe_"` in daemon/server.py (should be 0)
- `QEParameterBrowser` in gui/src/ (should be 0)
- `useQEParameterMetadata` in gui/src/ (should be 0)

**Acceptance criteria**:
- [ ] `python -m pytest tests/gates/test_no_qe_special_case.py -v` passes
- [ ] `grep -rn "_handle_detect_qe\|_handle_list_qe_\|_handle_set_qe_\|_handle_discover_qe_\|_handle_reload_qe_\|_handle_get_qe_\|_handle_import_step_from_qe" src/quantumvitas/daemon/server.py` = empty
- [ ] `grep -rn "listQeUiParameters\|listQeParameterMetadata" gui/src/` = empty
- [ ] `grep -rn "QEDetectionResult\|QEParameterBrowser\|useQEParameterMetadata" gui/src/` = empty
- [ ] `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — all pass

**Expected failure modes**:
1. Deleting a handler that is still called by old GUI code (must verify M5-M7 complete first)
2. Tests that directly call deleted RPCs — these tests need updating too
3. Breaking daemon startup if handler registration dict has stale entries

**Stop & Opus Audit**: YES. Final verification before declaring done.

---

## Known High-Risk Traps for Auto

1. **Confusing step_type_gen vs step_type_spec**: step.yaml stores ONLY step_type_spec. DTOs carry both. gen is derived, never stored. If Auto writes `step_type_gen` to any YAML file, it's a bug.

2. **Introducing mapping dicts**: The pure derivation rule says `spec = f"{PREFIX}_{gen}"`. Any dict that maps gen to spec independently is banned. Auto must not create `STEP_TYPE_MAP = {"scf": "qe_scf", ...}`.

3. **Leaving silent QE defaults**: Auto may fix visible fallbacks but miss the obscure ones in models.py or templates.py. The gate test catches this.

4. **Making tests depend on .tmp**: Test fixtures must use tmp_path or live in tests/. Never import from .tmp/.

5. **GUI mixing legacy and new types**: When adding new RPC types to qv.ts, Auto must not create duplicate interfaces. Old QE types should be deleted only in M8, not earlier.

6. **Accidentally reintroducing "bare step_type"**: DTOs must use `step_type_gen` and `step_type_spec`, never bare `step_type`. Gate test `test_no_bare_step_type.py` catches this.

7. **Writing ENGINE_ROLE to calculation.yaml**: ENGINE_ROLE is a driver attribute, NOT a calculation attribute. It must never appear in YAML files.

8. **Confusing engine_family in W90 demos**: W90 demos have `engine_family: qe` because the base family is QE. The w90 steps are companions. Auto might incorrectly set `engine_family: w90`.

9. **Breaking the create_calculation call chain**: Multiple callers feed into create_calculation (GUI dialog, CLI, templates, snapshot materialization). All must be updated consistently.

10. **Importing drivers in kernel code**: generalized_steps.py may need to query driver attributes but must do so through DriverRegistry, not by importing driver modules directly.

---

## Test Command (every milestone)

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Prompt Files

Each milestone has a dedicated prompt file for Cursor Auto:
- `PROMPT_M0.md` through `PROMPT_M8.md`

These are in this same directory (`docs/architecture/phase_gui_multi_engine/`).
