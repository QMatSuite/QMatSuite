# Implementation Plan: Engine supported_presets and ParamSpace Capability Migration

**Status**: Active  
**Created**: 2026-01-17  
**Owner**: AUTO (Cursor implementation worker)

---

## 0. Contracts (LAW - Non-Negotiable)

### A) Step-type Applicability (ParamSpace Only; Gen Steps Only)

- Step-type applicability MUST and ONLY be declared in **ParamSpace** (`ParamSpaceVariant.applies_to_step_types`)
- MUST use **gen/public step types** (e.g., "scf", not "pyscf_scf" or "orca_scf")
- Each preset dimension has a gen-step availability table (Applicable / NotApplicable) keyed by gen step type
- NO other layer (StepTypeSpec, engine backend, runner) may encode step applicability

### B) Preset Definition-Side Capability (ParamSpace Only)

Each preset may have up to two independent definitions:
1. **IR-dialect version**: compiles to IR patch keys in exactly one IR dialect (e.g., `ir.pw` or `ir.qc`)
2. **Engine-specific version**: for a specific engine backend (e.g., ORCA macro), compiles to engine-specific patch

Hard uniqueness rules:
- For a given preset: 0–1 IR-dialect version
- For a given preset + engine: 0–1 engine-specific version
- If >1 engine-specific version applies for same engine: **HARD ERROR** (no tie-breakers)
- If both IR and engine-specific exist for an engine: engine-specific supersedes IR

### C) Engine Consumption-Side Capability (Engine Backend SSOT)

- Every engine backend MUST declare `supported_presets: [...]` as SSOT for "this engine supports these presets"
- UI MUST only show presets supported by engine backend **AND** applicable by ParamSpace gen-step availability
- If engine declares a preset and that preset is IR-based, engine MUST materialize all required IR keys or fail loudly
- If engine declares a preset with engine-specific version for that engine, engine MUST use engine-specific path (supersedes IR)

---

## 1. Current-State Findings (Evidence Index)

| Finding | Evidence Location | Notes |
|---------|-------------------|-------|
| `StepTypeSpec.accepts_presets` defined | `src/quantumvitas/workflow/registry.py:49-50` | Dataclass field |
| `StepTypeSpec.allowed_dimensions` defined | `src/quantumvitas/workflow/registry.py:51-52` | Dataclass field |
| `list_accepting_presets()` uses StepTypeSpec | `src/quantumvitas/workflow/registry.py:646-651` | Returns spec.id where spec.accepts_presets |
| ParamSpace gen-step availability | `src/quantumvitas/presets/space_variant.py:34` | `applies_to_step_types: FrozenSet[str]` |
| Variant index by (step, dimension) | `src/quantumvitas/presets/variants_registry.py:149-158` | `VARIANT_BY_STEP_AND_DIMENSION` dict |
| QC precision variant applies to "scf" | `src/quantumvitas/presets/variants_registry.py:110` | `frozenset({"scf"})` |
| Dual-path materialization implemented | `src/quantumvitas/presets/variants_registry.py:367-399` | `engine.*` prefix check |
| Engine base class | `src/quantumvitas/engine/base.py:17-26` | `Engine` abstract class |
| Engine registry | `src/quantumvitas/engine/registry.py:15-35` | `EngineRegistry` class |
| **`supported_presets` does NOT exist** | N/A | Must be added to engine classes |
| No UI/CLI/API usage of accepts_presets | grep confirmed | Only registry + tests use it |

### Failing Tests (Pre-Existing)

| Test File | Test Name | Issue |
|-----------|-----------|-------|
| `test_qc_step_preset_acceptance.py` | `test_pyscf_scf_accepts_presets` | Asserts `spec.accepts_presets is True` but is False |
| `test_qc_step_preset_acceptance.py` | `test_orca_scf_accepts_presets` | Asserts `spec.accepts_presets is True` but is False |
| `test_qc_step_preset_acceptance.py` | `test_list_accepting_presets_includes_qc_steps` | Uses `list_accepting_presets()` which uses StepTypeSpec |

### Tests Using StepTypeSpec Capability Fields

| Test File | Location | Field Used |
|-----------|----------|------------|
| `test_qc_step_preset_acceptance.py` | lines 15-22, 25-32, 106-119, 122-135 | `accepts_presets`, `allowed_dimensions` |
| `test_workflow.py` | lines 68, 136-140 | `accepts_presets`, `allowed_dimensions` |
| `test_pyscf_integration.py` | line 53 | `accepts_presets` |

---

## 2. Discrepancy Log (Spec vs Current Code)

| Item | Spec Requirement | Current Code | Gap |
|------|------------------|--------------|-----|
| Step applicability SSOT | ParamSpace only | StepTypeSpec + ParamSpace | StepTypeSpec encodes duplicated truth |
| Engine supported_presets | Required | Does not exist | Must add to Engine classes |
| list_accepting_presets | Computed from engine.supported_presets ∩ ParamSpace | Uses StepTypeSpec.accepts_presets | Must rewrite function |
| Failing tests | Must pass | 3 failures | Must migrate tests to new contract |

---

## 3. PR Implementation Plan

### PR0: Add Engine.supported_presets and Deprecate StepTypeSpec Fields

**Scope**: Add `supported_presets` property to engine classes; mark StepTypeSpec fields as legacy

**Files to Touch**:
- [ ] `src/quantumvitas/engine/base.py` - Add abstract `supported_presets` property
- [ ] `src/quantumvitas/engine/qe_engine.py` - Implement `supported_presets` (return PW dimensions)
- [ ] `src/quantumvitas/engine/pyscf_engine.py` - Implement `supported_presets` (return `["qc_precision"]`)
- [ ] `src/quantumvitas/engine/orca_engine.py` - Implement `supported_presets` (return `["qc_precision"]`)
- [ ] `src/quantumvitas/workflow/registry.py` - Add deprecation comment to StepTypeSpec fields

**New Tests**:
- [ ] `tests/unit/test_engine_supported_presets.py` - Test each engine declares correct presets

**Pytest Commands**:
```bash
pytest tests/unit/test_engine_supported_presets.py -v
pytest tests/engine/test_pyscf_engine.py tests/engine/test_orca_engine.py -v --ignore=tests/unit/test_qc_step_preset_acceptance.py
```

**Stop Condition**: If engine import fails or probe() breaks, log evidence and stop.

---

### PR1: Add list_presets_for_engine() Function Using New Contract

**Scope**: Add function that computes available presets from engine.supported_presets ∩ ParamSpace applicability

**Files to Touch**:
- [ ] `src/quantumvitas/presets/variants_registry.py` - Add `list_dimensions_for_gen_step()` helper
- [ ] `src/quantumvitas/presets/catalog.py` - Add `list_presets_for_engine()` function
- [ ] `src/quantumvitas/workflow/registry.py` - Add `list_accepting_presets_for_engine()` that calls new function

**New Tests**:
- [ ] `tests/unit/test_preset_capability_contract.py` - Test new contract functions

**Pytest Commands**:
```bash
pytest tests/unit/test_preset_capability_contract.py -v
pytest tests/presets/ -v --ignore=tests/unit/test_qc_step_preset_acceptance.py
```

**Stop Condition**: If ParamSpace lookup fails or dimension not found, log evidence and stop.

---

### PR2: Migrate test_qc_step_preset_acceptance.py to New Contract

**Scope**: Rewrite failing tests to assert new contract (engine.supported_presets + ParamSpace applicability)

**Files to Touch**:
- [ ] `tests/unit/test_qc_step_preset_acceptance.py` - Rewrite 12 tests

**Test Migration Table**:

| Old Test | Old Assertion | New Assertion |
|----------|---------------|---------------|
| `test_pyscf_scf_accepts_presets` | `spec.accepts_presets is True` | `"qc_precision" in PySCFEngine().supported_presets` |
| `test_orca_scf_accepts_presets` | `spec.accepts_presets is True` | `"qc_precision" in ORCAEngine().supported_presets` |
| `test_pyscf_mp2_does_not_accept_presets` | `spec.accepts_presets is False` | `get_variant("qc_precision", "mp2") is None` (ParamSpace says N/A) |
| `test_pyscf_td_does_not_accept_presets` | `spec.accepts_presets is False` | `get_variant("qc_precision", "td") is None` |
| `test_orca_td_does_not_accept_presets` | `spec.accepts_presets is False` | `get_variant("qc_precision", "td") is None` |
| `test_pw_step_types_unchanged` | `spec.accepts_presets is True` + `allowed_dimensions` | `"precision" in QeEngine().supported_presets` + ParamSpace variant exists |
| `test_qc_precision_variant_applies_to_scf` | Already correct | Keep as-is (already tests ParamSpace) |
| `test_qc_precision_variant_does_not_apply_to_mp2` | Already correct | Keep as-is |
| `test_qc_precision_variant_does_not_apply_to_td` | Already correct | Keep as-is |
| `test_pyscf_scf_allowed_dimensions_only_qc_precision` | `spec.allowed_dimensions` | Test via ParamSpace + engine.supported_presets |
| `test_orca_scf_allowed_dimensions_only_qc_precision` | `spec.allowed_dimensions` | Test via ParamSpace + engine.supported_presets |
| `test_list_accepting_presets_includes_qc_steps` | `list_accepting_presets()` | Use new `list_accepting_presets_for_engine()` |

**Pytest Commands**:
```bash
pytest tests/unit/test_qc_step_preset_acceptance.py -v
```

**Stop Condition**: If imports break or new functions don't exist, log evidence and stop.

---

### PR3: Migrate Other Tests Using StepTypeSpec Capability Fields

**Scope**: Update remaining tests to not rely on StepTypeSpec.accepts_presets/allowed_dimensions

**Files to Touch**:
- [ ] `tests/unit/test_workflow.py` - Update lines 68, 136-140
- [ ] `tests/unit/test_pyscf_integration.py` - Update line 53

**Test Migration Table**:

| Test | Old Assertion | New Assertion |
|------|---------------|---------------|
| `test_workflow.py::test_get_step_type_spec` (line 68) | `spec.accepts_presets is True` | Remove or replace with ParamSpace check |
| `test_workflow.py::test_pw_dimensions_consistent` | `spec.allowed_dimensions == PW_DIMENSIONS` | Use ParamSpace query for dimensions |
| `test_pyscf_integration.py::test_pyscf_scf_spec_properties` (line 53) | `spec.accepts_presets is False` | Remove assertion (no longer relevant) |

**Pytest Commands**:
```bash
pytest tests/unit/test_workflow.py -v
pytest tests/unit/test_pyscf_integration.py -v
pytest tests/unit/ -v
```

**Stop Condition**: If test collection fails, log evidence and stop.

---

### PR4: Remove Legacy StepTypeSpec Fields (Optional - May Defer)

**Scope**: Remove `accepts_presets` and `allowed_dimensions` from StepTypeSpec after all tests migrated

**Files to Touch**:
- [ ] `src/quantumvitas/workflow/registry.py` - Remove fields from dataclass
- [ ] `src/quantumvitas/workflow/registry.py` - Remove `list_accepting_presets()` method (replaced)
- [ ] Remove field assignments from all step type definitions

**Pytest Commands**:
```bash
pytest tests/unit/ -v
pytest tests/integration/ -v --ignore=tests/integration/orca --ignore=tests/integration/pyscf
```

**Stop Condition**: If any test still references removed fields, log and stop.

---

## 4. AUTO Execution Log

Use this section to track progress. Tick checkboxes as tasks complete.

### PR0 Progress
- [x] Added `supported_presets` property to `Engine` base class
- [x] Implemented for `QeEngine`
- [x] Implemented for `PySCFEngine`
- [x] Implemented for `ORCAEngine`
- [x] Added deprecation comment to StepTypeSpec fields
- [x] Created `test_engine_supported_presets.py`
- [x] All PR0 tests pass

### PR1 Progress
- [x] Added `list_dimensions_for_gen_step()` to variants_registry.py
- [x] Added `list_presets_for_engine()` to catalog.py
- [x] Added `list_accepting_presets_for_engine()` to registry.py
- [x] Created `test_preset_capability_contract.py`
- [x] All PR1 tests pass

### PR2 Progress
- [ ] Migrated `test_pyscf_scf_accepts_presets`
- [ ] Migrated `test_orca_scf_accepts_presets`
- [ ] Migrated `test_pyscf_mp2_does_not_accept_presets`
- [ ] Migrated `test_pyscf_td_does_not_accept_presets`
- [ ] Migrated `test_orca_td_does_not_accept_presets`
- [ ] Migrated `test_pw_step_types_unchanged`
- [ ] Migrated `test_pyscf_scf_allowed_dimensions_only_qc_precision`
- [ ] Migrated `test_orca_scf_allowed_dimensions_only_qc_precision`
- [ ] Migrated `test_list_accepting_presets_includes_qc_steps`
- [ ] Kept 3 ParamSpace tests unchanged (already correct)
- [ ] All PR2 tests pass

### PR3 Progress
- [ ] Updated `test_workflow.py::test_get_step_type_spec`
- [ ] Updated `test_workflow.py::test_pw_dimensions_consistent`
- [ ] Updated `test_pyscf_integration.py::test_pyscf_scf_spec_properties`
- [ ] All PR3 tests pass
- [ ] Full unit test suite passes

### PR4 Progress (Optional)
- [ ] Removed StepTypeSpec.accepts_presets field
- [ ] Removed StepTypeSpec.allowed_dimensions field
- [ ] Removed list_accepting_presets() method
- [ ] Removed field assignments from step type definitions
- [ ] All tests pass

---

## 5. Test Migration Index

| Original Test | Original File | New Contract Tested | Migrated In |
|---------------|---------------|---------------------|-------------|
| test_pyscf_scf_accepts_presets | test_qc_step_preset_acceptance.py | Engine.supported_presets | PR2 |
| test_orca_scf_accepts_presets | test_qc_step_preset_acceptance.py | Engine.supported_presets | PR2 |
| test_pyscf_mp2_does_not_accept_presets | test_qc_step_preset_acceptance.py | ParamSpace gen-step availability | PR2 |
| test_pyscf_td_does_not_accept_presets | test_qc_step_preset_acceptance.py | ParamSpace gen-step availability | PR2 |
| test_orca_td_does_not_accept_presets | test_qc_step_preset_acceptance.py | ParamSpace gen-step availability | PR2 |
| test_pw_step_types_unchanged | test_qc_step_preset_acceptance.py | Engine.supported_presets + ParamSpace | PR2 |
| test_pyscf_scf_allowed_dimensions_only_qc_precision | test_qc_step_preset_acceptance.py | Engine.supported_presets | PR2 |
| test_orca_scf_allowed_dimensions_only_qc_precision | test_qc_step_preset_acceptance.py | Engine.supported_presets | PR2 |
| test_list_accepting_presets_includes_qc_steps | test_qc_step_preset_acceptance.py | list_accepting_presets_for_engine() | PR2 |
| test_get_step_type_spec | test_workflow.py | Remove accepts_presets assertion | PR3 |
| test_pw_dimensions_consistent | test_workflow.py | ParamSpace variant query | PR3 |
| test_pyscf_scf_spec_properties | test_pyscf_integration.py | Remove accepts_presets assertion | PR3 |

---

## 6. Evidence Log (For AUTO When Stuck)

Use this section to log evidence if stuck. Format:

```
[TIMESTAMP] [PR#] STUCK:
- Attempted: <action>
- Error: <error message>
- File: <path>:<line>
- Evidence: <relevant code snippet or state>
- Next Step Recommendation: <what to try or ask owner>
```

---

## End of Plan

