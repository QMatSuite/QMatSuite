# VASP Post-Implementation Test Fix Plan

**Date**: 2026-01-19  
**Author**: Opus (Architecture/Compliance Reviewer)  
**Purpose**: Detailed fix plan for 9 failing tests after VASP integration

---

## Executive Summary

VASP integration was completed strictly per the v2.0 plan. However, 9 tests are now failing due to **misalignment between existing tests (written pre-VASP) and the post-VASP reality**. The failures are NOT bugs in the VASP implementation—they are tests that need updating to reflect the now-larger supported engine ecosystem.

---

## 1. Root-Cause Map

### Root Cause A: Prefix Allowlist Not Updated (2 tests)

**Affected Tests**:
1. `tests/unit/test_step_type_mapping.py::TestStepTypeMappingCompleteness::test_all_keys_are_spec_step_types`
2. `tests/unit/test_step_type_mapping.py::TestStepTypeRegistryLookup::test_spec_type_preserved_in_registry`

**Problem**:
These tests have hardcoded prefix allowlists:
```python
valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_")
```

When VASP step types (`vasp_scf`, `vasp_nscf`, `vasp_bands`, `vasp_relax`) were added to `_STEP_TYPES` in `registry.py`, these tests started failing because `vasp_` is not in the allowlist.

**V2.0 Spec Alignment**:
Per `02_vasp_goals_and_required_behaviors.md` Section 1.2, VASP SPEC step types are:
- `vasp_scf`, `vasp_nscf`, `vasp_bands`, `vasp_relax`

These follow the same `{engine}_{step}` naming convention as other engines. The allowlist must be extended.

---

### Root Cause B: Phase3b Tests Assume VASP is Unsupported (6 tests)

**Affected Tests**:
1. `tests/unit/test_workflow_materialization_phase3b.py::TestUnsupportedFamilyMaterialization::test_unsupported_family_returns_none`
2. `tests/unit/test_workflow_materialization_phase3b.py::TestUnsupportedFamilyMaterialization::test_unsupported_family_workflow_raises_error`
3. `tests/unit/test_workflow_materialization_phase3b.py::TestUnsupportedFamilyMaterialization::test_mixed_supported_unsupported_workflow_raises_error`
4. `tests/unit/test_workflow_materialization_phase3b.py::TestUnsupportedFamilyMaterialization::test_pyscf_workflow_with_unsupported_raises_error`
5. `tests/unit/orca/test_workflow_integration.py::TestORCAMaterialization::test_unsupported_workflow_raises`
6. `tests/workflow/test_generalized_steps.py::TestGeneralizedStepMaterialization::test_materialize_workflow_fails_on_unsupported`

**Problem**:
These tests were written **before VASP integration** and use `"vasp"` as an example of an "unsupported engine family":

```python
# test_workflow_materialization_phase3b.py:91-92
def test_unsupported_family_returns_none(self):
    result = materialize_public_step_key("scf", "vasp")
    assert result is None  # <-- NOW RETURNS "vasp_scf"!
```

Now that VASP is fully implemented:
- `materialize_public_step_key("scf", "vasp")` returns `"vasp_scf"` (correct per spec)
- `materialize_workflow(["scf"], "vasp")` returns `["vasp_scf"]` (correct per spec)

**V2.0 Spec Alignment**:
Per `02_vasp_goals_and_required_behaviors.md`:
- VASP is now a fully supported engine family
- Tests using VASP as "unsupported" must switch to a truly unsupported family (e.g., `"abinit"`, `"crystal"`, `"unknown_engine"`)

**Critical Distinction**:
The v2.0 spec defines **two different "None" semantics**:

| Scenario | Return Value | Behavior |
|----------|--------------|----------|
| **0-mapping** (explicit) | `None` in MATERIALIZATION_MAP | Silent omission in `materialize_workflow()` |
| **Unsupported family** | `None` from lookup failure | `ValueError` in `materialize_workflow()` |

Current implementation has a **bug**: `materialize_workflow()` silently omits ALL None returns, including unsupported families. Per v2.0 spec Section 3.1, only **explicit 0-mappings** should be silently omitted.

---

### Root Cause C: StepType Import Detection Regex Too Broad (1 test)

**Affected Test**:
1. `tests/unit/test_no_steptype_enum.py::test_no_steptype_import_in_production`

**Problem**:
The test uses this regex:
```python
r"from.*StepType|import.*StepType"
```

This matches:
- `from quantumvitas.workflow.registry import StepTypeRegistry` ❌ (False positive!)
- `from quantumvitas.workflow.registry import StepTypeSpec` ❌ (False positive!)
- `from quantumvitas.workflow.registry import StepType` ✓ (Actual violation)

The file `src/quantumvitas/execution/reference_resolver.py` imports:
```python
from quantumvitas.workflow.registry import get_registry, StepTypeRegistry
```

This is **NOT** a violation—`StepTypeRegistry` is a class, not the forbidden `StepType` enum. The regex is incorrectly flagging it.

**V2.0 Spec Alignment**:
Per Constitution (referenced in test docstring): "Only gen/public step (str) and spec/machine step (str) are allowed."

The forbidden items are:
- `StepType` enum class
- `_coerce_step_type()` function

The allowed items are:
- `StepTypeRegistry` class
- `StepTypeSpec` dataclass

---

## 2. Code Pointers

### For Root Cause A (Prefix Allowlist)

**Files to Modify**:
- `tests/unit/test_step_type_mapping.py`
  - Function: `TestStepTypeMappingCompleteness.test_all_keys_are_spec_step_types` (line 23)
  - Function: `TestStepTypeRegistryLookup.test_spec_type_preserved_in_registry` (line 128)

**Change**: Add `"vasp_"` to `valid_prefixes` tuple.

---

### For Root Cause B (Unsupported Family Tests)

**Files to Modify**:

1. `tests/unit/test_workflow_materialization_phase3b.py`
   - Class: `TestUnsupportedFamilyMaterialization` (line 86)
   - Change: Replace `"vasp"` with `"abinit"` or another truly unsupported family
   - Note: `test_pyscf_only_scf_supported` and `test_pyscf_workflow_with_unsupported_raises_error` are likely still valid but need review

2. `tests/unit/orca/test_workflow_integration.py`
   - Function: `TestORCAMaterialization.test_unsupported_workflow_raises` (line 116)
   - Current test: `materialize_workflow(["scf", "bands"], "orca")`
   - Note: This may still be valid—ORCA doesn't support "bands". Review the actual behavior.

3. `tests/workflow/test_generalized_steps.py`
   - Function: `TestGeneralizedStepMaterialization.test_materialize_workflow_fails_on_unsupported` (line 50)
   - Change: Ensure the unsupported step/family combination is truly unsupported

**Production Code to Review/Fix**:

4. `src/quantumvitas/workflow/generalized_steps.py`
   - Function: `materialize_workflow()` (line 129)
   - Issue: Currently silently omits ALL None returns
   - Fix: Must distinguish between:
     - **0-mapping (explicit None in MATERIALIZATION_MAP)** → silent omission
     - **Unsupported family/step (lookup failure)** → raise ValueError

---

### For Root Cause C (Regex Too Broad)

**Files to Modify**:
- `tests/unit/test_no_steptype_enum.py`
  - Function: `test_no_steptype_import_in_production` (line 13)

**Change**: Use word-boundary regex:
```python
r"\bStepType\b"
```

Or more precise:
```python
r"(from|import).*\bStepType\b(?!Registry|Spec)"
```

---

## 3. Spec-Consistent Resolution

### Resolution for Root Cause A

**Approach**: Extend the prefix allowlist to include `vasp_`.

**Pseudocode**:
```python
# In test_step_type_mapping.py
valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_", "vasp_")
```

**Why This Works**: 
- Per v2.0 spec, VASP step types follow the standard `{engine}_{step}` naming convention
- The test's purpose is to ensure ALL registered step types have valid engine prefixes
- Adding `vasp_` makes the test accurately reflect the post-VASP registry state

---

### Resolution for Root Cause B

**Approach**: Two-pronged fix:

1. **Fix Tests**: Replace `"vasp"` with a truly unsupported engine family in test assertions

2. **Fix Production Code**: Modify `materialize_workflow()` to distinguish 0-mapping from unsupported

**Pseudocode for Production Fix**:
```python
def materialize_workflow(
    generalized_steps: list[str],
    engine_family: str,
) -> list[str]:
    """
    Per VASP integration plan v2.0:
    - 0-mapping steps (explicit None in MATERIALIZATION_MAP) are silently omitted
    - Unsupported family/step combinations raise ValueError
    """
    result = []
    unsupported_steps = []
    
    for gen_step in generalized_steps:
        specific_step = materialize_public_step_key(gen_step, engine_family)
        
        if specific_step is None:
            # Check if this is an explicit 0-mapping vs truly unsupported
            if _is_zero_mapping(gen_step, engine_family):
                # 0-mapping: silently omit (per v2.0 spec)
                continue
            else:
                # Truly unsupported: collect for error
                unsupported_steps.append(gen_step)
        else:
            result.append(specific_step)
    
    if unsupported_steps:
        raise ValueError(
            f"Steps {unsupported_steps} are not supported by engine family '{engine_family}'"
        )
    
    return result

def _is_zero_mapping(gen_step: str, engine_family: str) -> bool:
    """Check if (engine_family, gen_step) is explicitly mapped to None in MATERIALIZATION_MAP."""
    key = (engine_family.lower(), gen_step.upper())
    return key in MATERIALIZATION_MAP and MATERIALIZATION_MAP[key] is None
```

**Why This Works**:
- Explicit 0-mappings (like `("vasp", "BANDS_POST"): None`) are silently omitted
- Unknown combinations that aren't in MATERIALIZATION_MAP at all raise ValueError
- This matches the v2.0 spec exactly

---

### Resolution for Root Cause C

**Approach**: Refine the regex to use word boundaries and exclude `StepTypeRegistry`/`StepTypeSpec`.

**Pseudocode**:
```python
def test_no_steptype_import_in_production():
    """Production code must not import StepType enum."""
    # Match "StepType" but NOT "StepTypeRegistry" or "StepTypeSpec"
    matching_files = scan_for_pattern_list_files(r"\bStepType\b(?!Registry|Spec)")
    # ... rest of test
```

**Why This Works**:
- `\b` ensures word boundary (no partial matches)
- Negative lookahead `(?!Registry|Spec)` excludes the allowed class names
- The Constitution prohibition is specifically against the `StepType` enum, not the registry/spec classes

---

## 4. Cursor Auto Execution Plan

### Phase 1: Fix Prefix Allowlist (Low Risk)

**Goal**: Update prefix allowlist to include `vasp_`

**Files to Modify**:
- `tests/unit/test_step_type_mapping.py`

**Changes**:
1. Line 23: Change `valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_")` to `valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_", "vasp_")`
2. Line 128: Same change

**Expected Tests to Turn Green**:
- `test_all_keys_are_spec_step_types`
- `test_spec_type_preserved_in_registry`

**Verification Command**:
```bash
pytest tests/unit/test_step_type_mapping.py -v --tb=short
```

**Risk/Rollback**: Very low risk. Reverts cleanly.

---

### Phase 2: Fix StepType Detection Regex (Low Risk)

**Goal**: Refine regex to not match `StepTypeRegistry`/`StepTypeSpec`

**Files to Modify**:
- `tests/unit/test_no_steptype_enum.py`

**Changes**:
1. Line 15: Change pattern from `r"from.*StepType|import.*StepType"` to `r"\bStepType\b(?!Registry|Spec)"`

**Expected Tests to Turn Green**:
- `test_no_steptype_import_in_production`

**Verification Command**:
```bash
pytest tests/unit/test_no_steptype_enum.py -v --tb=short
```

**Risk/Rollback**: Very low risk. May need adjustment if regex engine doesn't support lookahead.

---

### Phase 3: Fix Unsupported Family Tests (Medium Risk)

**Goal**: Replace `"vasp"` with truly unsupported engine in test assertions

**Files to Modify**:
- `tests/unit/test_workflow_materialization_phase3b.py`

**Changes**:
1. Replace all occurrences of `"vasp"` with `"abinit"` (or another unsupported engine) in class `TestUnsupportedFamilyMaterialization`

Specifically:
- Line 91: `materialize_public_step_key("scf", "abinit")` → expects `None`
- Line 96: `materialize_workflow(["scf"], "abinit")` → expects `ValueError`
- Line 101: `materialize_workflow(["scf", "nscf"], "abinit")` → expects `ValueError`

**DO NOT CHANGE**:
- Tests in `TestQEFamilyMaterialization` (QE is fully supported)
- `test_pyscf_only_scf_supported` (PySCF partial support is still accurate)

**Expected Tests to Turn Green**:
- `test_unsupported_family_returns_none`
- `test_unsupported_family_workflow_raises_error`
- `test_mixed_supported_unsupported_workflow_raises_error`

**Verification Command**:
```bash
pytest tests/unit/test_workflow_materialization_phase3b.py -v --tb=short
```

**Risk/Rollback**: Medium risk. Must ensure "abinit" is truly unsupported.

---

### Phase 4: Fix materialize_workflow 0-mapping vs Unsupported Semantics (Medium Risk)

**Goal**: Fix `materialize_workflow()` to distinguish 0-mapping from unsupported

**Files to Modify**:
- `src/quantumvitas/workflow/generalized_steps.py`

**Changes**:
1. Add helper function `_is_zero_mapping(gen_step, engine_family)` to check if a step is explicitly mapped to None
2. Modify `materialize_workflow()` to:
   - Silently omit only explicit 0-mappings
   - Collect unsupported steps and raise ValueError at end

**Implementation Guidance**:
```python
def _is_zero_mapping(gen_step: str, engine_family: str) -> bool:
    """
    Check if (engine_family, gen_step) is explicitly mapped to None.
    
    Returns True only if the key exists in MATERIALIZATION_MAP with value None.
    Returns False if the key is not in the map at all.
    """
    key = (engine_family.lower(), gen_step.upper())
    return key in MATERIALIZATION_MAP and MATERIALIZATION_MAP[key] is None

def materialize_workflow(generalized_steps: list[str], engine_family: str) -> list[str]:
    result = []
    unsupported_steps = []
    
    for gen_step in generalized_steps:
        specific_step = materialize_public_step_key(gen_step, engine_family)
        
        if specific_step is None:
            # Distinguish 0-mapping from unsupported
            if _is_zero_mapping(gen_step, engine_family):
                # Explicit 0-mapping: silently omit (per v2.0 spec)
                continue
            else:
                # Truly unsupported: collect for error
                unsupported_steps.append(gen_step)
        else:
            result.append(specific_step)
    
    if unsupported_steps:
        raise ValueError(
            f"Steps {unsupported_steps} not supported by engine family '{engine_family}'"
        )
    
    return result
```

**Expected Tests to Turn Green**:
- `test_pyscf_workflow_with_unsupported_raises_error`
- `test_unsupported_workflow_raises` (ORCA test)
- `test_materialize_workflow_fails_on_unsupported`

**Verification Command**:
```bash
pytest tests/unit/test_workflow_materialization_phase3b.py tests/unit/orca/test_workflow_integration.py tests/workflow/test_generalized_steps.py -v --tb=short
```

**Risk/Rollback**: Medium risk. May affect other workflows. Run full test suite after.

---

### Phase 5: Full Regression Test

**Goal**: Verify all 9 failing tests pass AND no regressions

**Verification Commands**:
```bash
# Run previously failing tests
pytest tests/unit/test_step_type_mapping.py tests/unit/test_workflow_materialization_phase3b.py tests/unit/test_no_steptype_enum.py tests/unit/orca/test_workflow_integration.py tests/workflow/test_generalized_steps.py -v --tb=short

# Run full VASP test suite
pytest tests/unit/test_vasp_*.py tests/integration/vasp/ -v --tb=short -n auto

# Run full test suite (parallel)
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Success Criteria**:
- All 9 previously failing tests pass
- All 58 VASP-related tests pass
- No new regressions in full test suite

---

## 5. Guidance (No Production Code)

### 5.1 Prefix Allowlist Synchronization

**Pattern**: The prefix allowlist should be derived from registry, not hardcoded.

**Future-Proof Alternative** (for consideration, not required for this fix):
```python
def get_valid_engine_prefixes() -> tuple:
    """Derive valid prefixes from registered step types."""
    from quantumvitas.workflow.registry import _STEP_TYPES
    prefixes = set()
    for machine_type in _STEP_TYPES.keys():
        prefix = machine_type.split('_')[0] + '_'
        prefixes.add(prefix)
    return tuple(sorted(prefixes))
```

For this fix, simply add `"vasp_"` to the hardcoded tuple.

---

### 5.2 Distinguishing 0-Mapping from Unsupported

**Key Insight**: The MATERIALIZATION_MAP has two types of "None" semantics:

| Entry | Meaning |
|-------|---------|
| `("vasp", "BANDS_POST"): None` | Explicit 0-mapping (supported engine, unsupported step for that engine) |
| Key not in map | Truly unsupported (unknown engine or step) |

**Detection Logic**:
```python
def _is_zero_mapping(gen_step: str, engine_family: str) -> bool:
    key = (engine_family.lower(), gen_step.upper())
    # Key MUST exist and map to None for it to be a 0-mapping
    return key in MATERIALIZATION_MAP and MATERIALIZATION_MAP[key] is None
```

**Behavior Matrix**:

| `materialize_public_step_key()` returns | `_is_zero_mapping()` returns | `materialize_workflow()` behavior |
|----------------------------------------|------------------------------|-----------------------------------|
| `"vasp_scf"` (string) | N/A | Append to result |
| `None` | `True` | Silent omit (0-mapping) |
| `None` | `False` | Collect as unsupported, raise ValueError at end |

---

### 5.3 Unsupported Family Definition

An engine family is **unsupported** if it has **no entries** in MATERIALIZATION_MAP.

Current supported families (have entries):
- `qe`
- `pyscf`
- `orca`
- `vasp`

Unsupported families (no entries, safe for tests):
- `abinit`
- `crystal`
- `unknown_engine`
- `foobar`

Tests should use one of the unsupported families when testing error paths.

---

### 5.4 StepType vs StepTypeRegistry/StepTypeSpec

**Forbidden**:
- `StepType` (the enum class) - violates Constitution
- `_coerce_step_type()` - deprecated function

**Allowed**:
- `StepTypeRegistry` - the registry class
- `StepTypeSpec` - the spec dataclass
- `get_registry()` - registry accessor

The regex pattern must use negative lookahead to exclude the allowed names:
```python
r"\bStepType\b(?!Registry|Spec)"
```

This matches:
- `StepType` ✓
- `from foo import StepType` ✓

This does NOT match:
- `StepTypeRegistry` ✗
- `StepTypeSpec` ✗
- `from foo import StepTypeRegistry` ✗

---

### 5.5 reference_resolver.py and the GEN Type Check

The `reference_resolver.py` correctly uses registry lookup instead of the StepType enum:

```python
spec = registry.get(str(step_type))
if spec:
    step_public_type = spec.public_type
```

This is the **correct pattern** per Constitution. The file imports `StepTypeRegistry` (allowed) not `StepType` (forbidden).

---

## 6. Summary of Changes

| Phase | File | Change | Tests Fixed |
|-------|------|--------|-------------|
| 1 | `tests/unit/test_step_type_mapping.py` | Add `"vasp_"` to prefix allowlist | 2 |
| 2 | `tests/unit/test_no_steptype_enum.py` | Fix regex to use word boundaries | 1 |
| 3 | `tests/unit/test_workflow_materialization_phase3b.py` | Replace `"vasp"` with `"abinit"` | 3 |
| 4 | `src/quantumvitas/workflow/generalized_steps.py` | Add `_is_zero_mapping()`, fix `materialize_workflow()` | 3 |

**Total Tests Fixed**: 9

---

## 7. Risk Assessment

| Phase | Risk Level | Rollback Complexity |
|-------|------------|---------------------|
| 1 (Prefix) | Low | Simple revert |
| 2 (Regex) | Low | Simple revert |
| 3 (Test Family) | Medium | Simple revert |
| 4 (materialize_workflow) | Medium | May need careful testing |

**Recommendation**: Execute phases 1-3 first, verify, then proceed to phase 4.

---

## Appendix: Test Failure Details

### Test 1: test_all_keys_are_spec_step_types
```
AssertionError: Key 'vasp_scf' is not a valid SPEC step type. SPEC step types must start with one of: ('qe_', 'w90_', 'pyscf_', 'orca_')
```

### Test 2: test_spec_type_preserved_in_registry
```
AssertionError: Machine type 'vasp_scf' is not in SPEC format. Expected prefix from: ('qe_', 'w90_', 'pyscf_', 'orca_')
```

### Tests 3-7: Various materialize_workflow tests
```
Expected ValueError but None was returned / no exception raised
```

### Test 8: test_materialize_workflow_fails_on_unsupported
```
ValueError not raised for unsupported step
```

### Test 9: test_no_steptype_import_in_production
```
Found StepType import in production code: src/quantumvitas/execution/reference_resolver.py
```
(False positive due to `StepTypeRegistry` import)

