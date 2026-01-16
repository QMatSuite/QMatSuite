# Final Audit: IR Truth + Step Vocabulary SSOT — Executive Memo

**Date**: 2025-01-XX  
**Purpose**: Final conclusions from deep audit resolving two disputed points: (A) IR representation truth, (B) Step vocabulary SSOT.

---

## Part A: IR Representation Truth — Final Answer

### Truth Statement

**"IR is QE-canonical and stored as strings in YAML; `.true.`/`.false.` appear before the writer."**

### Evidence Summary

1. **ParamSpace compiler output**: `src/quantumvitas/presets/paramspace.py:601-605`
   - Converts Python `bool` to `.true.`/`.false.` strings using `ir_bool()`
   - Patch dicts contain IR canonical strings, not Python bool

2. **Integration layer**: `src/quantumvitas/presets/integration.py:712-720`
   - Calls `ir_params_to_qe_params()` to ensure QE format before applying to StepDoc
   - Comment: "step.yaml is spec step, parameters must be engine-specific format (QE: .true./.false.)"

3. **Step YAML storage**: `src/quantumvitas/core/yamldoc.py:apply_patch()` (lines 358-396)
   - Stores values as-is via `set()` (line 396)
   - If patch contains `.true.` string, it is stored as string (preserved)

4. **Test evidence**: `tests/presets/test_integration_ir.py:177`
   - Expects `.false.` string in step.yaml after applying presets
   - Comment: "step.yaml stores QE strings, not Python bools"

5. **QE writer**: `src/quantumvitas/ir/backends/qe/mapping.py:ir_to_qe_param()` (lines 118-122)
   - Converts Python `bool` to `.true.`/`.false.` strings for boolean parameters
   - If input is already `.true.` string, it passes through unchanged

### Verification Needed

**UNKNOWN**: Does `yaml.safe_load()` parse `noncolin: .true.` as string or boolean?

**Proposed test**:
```python
def test_yaml_boolean_parsing():
    import yaml
    data = yaml.safe_load("noncolin: .true.")
    assert isinstance(data["noncolin"], str)  # Should be string, not bool
```

**If YAML parses as boolean**: Materialization must handle type conversion (QE writer already handles this).

---

## Part B: Step Vocabulary SSOT — Final Answer

### Two Real Vocabularies

1. **Gen/Public Step Types** (e.g., `"scf"`, `"nscf"`)
   - **Used by**: Presets/ParamSpace (`variants_registry.py:257-265`), UI display (`api.py:3438-3439`), file naming (`api.py:3437`)
   - **Storage**: Not stored on disk (in-memory only)
   - **SSOT**: `StepTypeRegistry` `public_type` field

2. **Spec/Machine Step Types** (e.g., `"qe_scf"`, `"w90_run"`)
   - **Used by**: step.yaml storage (`step_factory.py:73`), runner execution (`step.py:92`, `qe_engine.py:40-41`), materialization (`structure_steps.py:747-772`)
   - **Storage**: Stored in `step.yaml` `step_type` field
   - **SSOT**: `StepTypeRegistry` `machine_type` field

### StepType Enum Status

**Classification**: **Legacy-only compatibility layer**

**Acceptable usages** (coercion/formatting only):
- `Step.step_type` field (step.py:29) - Type hinting
- `_coerce_step_type()` (runner.py:50-77) - String to Enum conversion
- API response formatting (api.py:1292, 2376) - Response serialization

**NOT acceptable usages** (core logic violations):
- `api.py:7756-7758` - Validation logic for relax operations
- `api.py:7866-7868` - Same validation (duplicate)

**Impact for ORCA/PySCF**: **HIGH** - Enum validation will fail for ORCA/PySCF steps because Enum doesn't include their values.

**Fix required**: Replace Enum checks with `StepTypeRegistry` lookups.

### Mapping Logic

**Single source of truth**: `StepTypeRegistry.get()` (workflow/registry.py:594-618)
- Accepts both `public_type` and `machine_type`
- Returns `StepTypeSpec` with both fields
- **No multiple mappings exist** (safe)

---

## Part C: ORCA/PySCF Onboarding Implications

### What to Implement

1. **Step type registry entries**: Add `StepTypeSpec` entries to `_STEP_TYPES` dict
   - Example: `StepTypeSpec(id="scf", machine_type="orca_scf", public_type="scf", engine="orca", ...)`

2. **Preset variants**: Add variant entries with `applies_to_step_types` including ORCA/PySCF public types
   - Use `public_type` strings (e.g., `"scf"`), not `machine_type` (e.g., `"orca_scf"`)

3. **IR→engine mapping**: Create `ir/backends/{engine}/mapping.py`
   - Implement `IR_TO_ORCA_MAPPING` or `IR_TO_PYSCF_MAPPING` dicts
   - Implement `ir_to_orca_param()` or `ir_to_pyscf_param()` functions
   - Convert IR canonical strings (`.true.`/`.false.`) to engine-specific format

4. **Fix Enum validation**: Replace `StepType` Enum checks with `StepTypeRegistry` lookups
   - Files: `api.py:7756-7758`, `api.py:7866-7868`

### What Must Remain Stable

- ParamSpace core semantics (key ownership, compile phases, oracle)
- species_map SSOT (calculation-level authoritative)
- Execution mode boundaries (project/standalone/compat)
- Type formatting boundary (ParamSpace writes IR canonical strings; engine writers convert)

### Risks and Mitigations

**Risk**: IR canonical strings (`.true.`/`.false.`) are QE-specific. ORCA/PySCF may use different boolean representations.

**Mitigation**: Engine writers must convert IR canonical strings to engine-specific format. This is acceptable because conversion happens at writer boundary (not in ParamSpace core).

**Recommendation**: Keep IR canonical strings as QE format for now. Convert to engine-specific format in writers (Path A). Alternative (Path B): Introduce engine-agnostic IR canonical format, but this requires more changes.

---

## Evidence Index

### IR Representation

- `src/quantumvitas/presets/paramspace.py:601-605` - ParamSpace compiler converts bool to `.true.`/`.false.`
- `src/quantumvitas/presets/integration.py:712-720` - Integration layer ensures QE format
- `src/quantumvitas/ir/backends/qe/mapping.py:14-41` - `ir_bool()` encoder
- `src/quantumvitas/ir/backends/qe/mapping.py:218-278` - `ir_params_to_qe_params()` converter
- `tests/presets/test_integration_ir.py:177` - Test expects `.false.` string

### Step Vocabulary

- `src/quantumvitas/workflow/registry.py:StepTypeSpec` (lines 23-58) - Gen/public and spec/machine definitions
- `src/quantumvitas/workflow/step_factory.py:73` - step.yaml stores machine_type
- `src/quantumvitas/presets/variants_registry.py:257-265` - Presets use public_type
- `src/quantumvitas/calculation/step.py:92` - Runner reads from step.yaml (machine_type)
- `src/quantumvitas/calculation/types.py:StepType` (lines 10-30) - Enum definition
- `src/quantumvitas/api.py:7756-7758` - Enum validation (SSOT violation)

---

## What to Do Next

1. **Verify YAML parsing**: Add test to confirm `yaml.safe_load()` behavior with `.true.`/`.false.` strings
2. **Fix Enum validation**: Replace `StepType` Enum checks in `api.py:7756-7758` and `7866-7868` with `StepTypeRegistry` lookups
3. **Document IR canonical format**: Update contract docs to explicitly state IR uses QE-canonical strings (`.true.`/`.false.`)
4. **Plan ORCA/PySCF mapping**: Design `IR_TO_ORCA_MAPPING` and `IR_TO_PYSCF_MAPPING` dicts
5. **Implement engine writers**: Create `ir/backends/{engine}/mapping.py` modules with boolean conversion logic

---

**End of Memo**

