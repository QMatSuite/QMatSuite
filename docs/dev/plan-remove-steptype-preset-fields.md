# Implementation Plan: Remove StepTypeSpec.accepts_presets and allowed_dimensions

**Status**: Ready for Implementation  
**Created**: 2026-01-17  
**Owner**: AUTO (Cursor implementation worker)

---

## 0. Review Summary

### A) Current State

**Fields to remove** (defined in `src/quantumvitas/workflow/registry.py`):
- `StepTypeSpec.accepts_presets: bool` (line 53)
- `StepTypeSpec.allowed_dimensions: FrozenSet[str]` (line 54)

**Deprecated method to remove**:
- `StepTypeRegistry.list_accepting_presets()` (lines 649-659)

**Constants to remove** (duplicates of `presets/dimensions.py`):
- `DIMENSION_MAGNETISM` (line 68)
- `DIMENSION_OCCUPATIONS` (line 69)
- `DIMENSION_PRECISION` (line 70)
- `PW_DIMENSIONS` (line 73)

### B) Evidence Commands (ripgrep verification)

```bash
# All accepts_presets references in production code
rg "accepts_presets" src/quantumvitas

# All allowed_dimensions references in production code
rg "allowed_dimensions" src/quantumvitas

# All references in tests
rg "accepts_presets|allowed_dimensions" tests

# PW_DIMENSIONS constant usage
rg "PW_DIMENSIONS" src/quantumvitas

# Deprecated method usage
rg "list_accepting_presets\(\)" src/quantumvitas tests

# StepTypeSpec field access in production
rg "spec\.accepts_presets|spec\.allowed_dimensions" src/quantumvitas
```

### C) Current SSOT (What Replaces Removed Fields)

| Purpose | Old (Removed) | New SSOT |
|---------|---------------|----------|
| Engine supports which presets | `allowed_dimensions` on all step types for engine | `Engine.supported_presets` property |
| Gen step accepts which presets | `accepts_presets` + `allowed_dimensions` on step type | `ParamSpaceVariant.applies_to_step_types` |
| Unified query | `list_accepting_presets()` | `list_presets_for_engine(engine_name, gen_step)` |
| Registry method | `list_accepting_presets()` | `list_accepting_presets_for_engine(engine_name)` |

### D) Production Code References (All in registry.py)

| Line | Reference | Action |
|------|-----------|--------|
| 35-36 | Docstring for fields | Remove lines |
| 50-54 | Field definitions + deprecation comments | Remove lines |
| 68-73 | Dimension constants + PW_DIMENSIONS | Remove block |
| 195-556 | 22 StepTypeSpec instantiations with fields | Remove field kwargs |
| 649-659 | `list_accepting_presets()` method | Remove method |

### E) Test References

| File | Line(s) | Reference | Action |
|------|---------|-----------|--------|
| `test_workflow.py` | 102-113 | `test_list_accepting_presets` | Delete test (tests deprecated method) |
| `test_workflow.py` | 68 | Comment about deprecation | No action (comment only) |
| `test_pyscf_integration.py` | 53 | Comment about deprecation | No action (comment only) |
| `test_qc_step_preset_acceptance.py` | 23,31,104,112 | Function names only | No action (uses new API) |

### F) No References Found In

- `gui/` - No references
- `src/quantumvitas/cli/` - No references
- `src/quantumvitas/daemon/` - No references
- `src/quantumvitas/api.py` - No references
- Any YAML schema files - No references

---

## 1. PR Checklist

### PR0: Remove StepTypeSpec fields and deprecated method

**Scope**: Remove fields, constants, and deprecated method from registry.py

**Files to modify**:
- `src/quantumvitas/workflow/registry.py`

**Changes**:

- [x] A) Remove docstring lines 35-36 (accepts_presets/allowed_dimensions descriptions)
- [x] B) Remove field definitions lines 53-54 (with deprecation comments)
- [x] C) Remove constant block lines 68-73 (DIMENSION_* and PW_DIMENSIONS)
- [x] D) Remove `accepts_presets=...` from all 22 StepTypeSpec instantiations
- [x] E) Remove `allowed_dimensions=...` from all 22 StepTypeSpec instantiations
- [x] F) Remove `list_accepting_presets()` method (lines 649-659)

**Verification commands (must all pass)**:

```bash
# Verify no accepts_presets references remain
rg "accepts_presets" src/quantumvitas/workflow/registry.py
# Expected: No matches

# Verify no allowed_dimensions references remain
rg "allowed_dimensions" src/quantumvitas/workflow/registry.py
# Expected: No matches

# Verify no PW_DIMENSIONS references remain
rg "PW_DIMENSIONS" src/quantumvitas/workflow/registry.py
# Expected: No matches

# Verify StepTypeSpec still imports correctly
python -c "from quantumvitas.workflow.registry import StepTypeSpec; print('OK')"

# Verify registry still works
python -c "from quantumvitas.workflow.registry import get_registry; r = get_registry(); print('step types:', len(r.list_all()))"
```

**Stop condition**: If imports fail or registry.list_all() returns 0 step types, STOP and create forensic note.

---

### PR1: Remove deprecated test

**Scope**: Remove test that calls deprecated method

**Files to modify**:
- `tests/unit/test_workflow.py`

**Changes**:

- [x] A) Remove `test_list_accepting_presets` method (lines 102-113)

**Verification commands**:

```bash
# Run workflow tests
pytest tests/unit/test_workflow.py -v -x

# Verify no test references deprecated method
rg "list_accepting_presets\(\)" tests
# Expected: No matches for parentheses version (only method signature in test_preset_capability_contract.py should remain)
```

**Stop condition**: If test collection fails, STOP and check for syntax errors.

---

### PR2: Add no-regression guard test

**Scope**: Add test that verifies production code does not reference removed fields

**Files to create**:
- `tests/unit/test_no_deprecated_preset_fields.py`

**Test content** (exact code for Auto):

```python
"""
Guard test: Ensure deprecated StepTypeSpec preset fields are removed.

This test fails if any production code references:
- StepTypeSpec.accepts_presets
- StepTypeSpec.allowed_dimensions
- list_accepting_presets() method
- PW_DIMENSIONS constant
"""

import pytest
import subprocess


def test_no_accepts_presets_in_production_code():
    """Production code must not reference accepts_presets field."""
    result = subprocess.run(
        ["rg", "-l", r"\.accepts_presets", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found accepts_presets field reference in production code:\n{matching_files}"
    )


def test_no_allowed_dimensions_in_production_code():
    """Production code must not reference allowed_dimensions field."""
    result = subprocess.run(
        ["rg", "-l", r"\.allowed_dimensions", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found allowed_dimensions field reference in production code:\n{matching_files}"
    )


def test_no_pw_dimensions_in_production_code():
    """Production code must not reference PW_DIMENSIONS constant."""
    result = subprocess.run(
        ["rg", "-l", r"PW_DIMENSIONS", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found PW_DIMENSIONS constant reference in production code:\n{matching_files}"
    )


def test_no_deprecated_list_accepting_presets():
    """Production code must not have deprecated list_accepting_presets() method."""
    result = subprocess.run(
        ["rg", "-l", r"def list_accepting_presets\(self\)", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found deprecated list_accepting_presets() method:\n{matching_files}"
    )


def test_steptypespec_has_no_preset_fields():
    """StepTypeSpec dataclass must not have preset-related fields."""
    from quantumvitas.workflow.registry import StepTypeSpec
    import dataclasses
    
    field_names = [f.name for f in dataclasses.fields(StepTypeSpec)]
    
    assert "accepts_presets" not in field_names, (
        "StepTypeSpec still has accepts_presets field"
    )
    assert "allowed_dimensions" not in field_names, (
        "StepTypeSpec still has allowed_dimensions field"
    )


def test_registry_has_no_deprecated_method():
    """StepTypeRegistry must not have deprecated list_accepting_presets() method."""
    from quantumvitas.workflow.registry import StepTypeRegistry
    
    assert not hasattr(StepTypeRegistry, "list_accepting_presets"), (
        "StepTypeRegistry still has deprecated list_accepting_presets() method"
    )
```

**Verification commands**:

```bash
# Run guard tests
pytest tests/unit/test_no_deprecated_preset_fields.py -v

# All should pass after PR0 and PR1 are complete
```

**Stop condition**: If any guard test fails after PR0 and PR1, there are leftover references. STOP and investigate.

---

### PR3: Final verification

**Scope**: Run full test suite and verify no regressions

**No files to modify** - verification only

**Verification commands**:

```bash
# Run all unit tests
pytest tests/unit/ -v --tb=short

# Run preset capability tests specifically
pytest tests/unit/test_preset_capability_contract.py -v
pytest tests/unit/test_qc_step_preset_acceptance.py -v
pytest tests/unit/test_engine_supported_presets.py -v

# Verify new SSOT API works
python -c "
from quantumvitas.presets.catalog import list_presets_for_engine
from quantumvitas.workflow.registry import get_registry

# QE SCF should have precision, magnetism, etc.
qe_scf = list_presets_for_engine('qe', 'scf')
print('QE SCF presets:', qe_scf)
assert 'precision' in qe_scf

# PySCF SCF should have qc_precision
pyscf_scf = list_presets_for_engine('pyscf', 'scf')
print('PySCF SCF presets:', pyscf_scf)
assert 'qc_precision' in pyscf_scf

# Registry method should work
registry = get_registry()
qe_result = registry.list_accepting_presets_for_engine('qe')
print('QE accepting presets:', qe_result)
assert 'scf' in qe_result

print('All SSOT API checks passed!')
"
```

**Stop condition**: If unit tests fail or SSOT API checks fail, STOP and investigate.

---

## 2. Acceptance Criteria

After all PRs complete:

1. [ ] `StepTypeSpec` dataclass has no `accepts_presets` or `allowed_dimensions` fields
2. [ ] `StepTypeRegistry` has no `list_accepting_presets()` method
3. [ ] No production code references `.accepts_presets` or `.allowed_dimensions`
4. [ ] No production code references `PW_DIMENSIONS`
5. [ ] Guard tests in `test_no_deprecated_preset_fields.py` all pass
6. [ ] `list_presets_for_engine()` is the SSOT API for capability queries
7. [ ] `list_accepting_presets_for_engine()` works correctly
8. [ ] All unit tests pass

---

## 3. Evidence Log (For AUTO When Stuck)

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

