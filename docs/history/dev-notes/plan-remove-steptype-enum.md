# Implementation Plan: Remove StepType Enum

**Status**: Review Complete  
**Decision**: **Staged Removal (Delete Enum)**  
**Rationale**: StepType Enum is a 3rd truth source that mixes gen/spec vocabularies, violating SSOT. Since it's not used for persistence and core logic already uses registry lookup, deletion is feasible.

---

## 1. Review Findings (Evidence)

### 1.1 Definition Location

**File**: `src/quantumvitas/calculation/types.py` (lines 10-30)

```python
class StepType(str, Enum):
    SCF = "scf"
    NSCF = "nscf"
    DOS = "dos"
    BANDS_PW = "bands_pw"
    BANDS = "bands"
    PH = "ph"
    Q2R = "q2r"
    MATDYN = "matdyn"
    DYNMAT = "dynmat"
    PP = "pp"
    PROJWFC = "projwfc"
    RELAX = "relax"
    VC_RELAX = "vc-relax"
    W90_PREPROC = "w90_preproc"
    PW2WANNIER90 = "pw2wannier90"
    W90_RUN = "w90_run"
    PYSCF_SCF = "pyscf_scf"
    CUSTOM = "custom"
```

### 1.2 SSOT Violation Analysis

The enum **mixes gen and spec vocabularies**:

| Value | Type | Issue |
|-------|------|-------|
| `SCF = "scf"` | GEN | OK - public type |
| `NSCF = "nscf"` | GEN | OK - public type |
| `BANDS_PW = "bands_pw"` | ??? | Unclear - no engine prefix |
| `W90_PREPROC = "w90_preproc"` | SPEC-like | Uses w90_ prefix |
| `PYSCF_SCF = "pyscf_scf"` | SPEC | Full machine type |

**Conclusion**: This enum is a 3rd vocabulary that doesn't cleanly map to either gen or spec.

### 1.3 Production Code Usage

| File | Usage | Notes |
|------|-------|-------|
| `calculation/step.py:29` | `step_type: Optional[StepType] = None` | Field in Step dataclass |
| `calculation/results.py:18` | `step_type: StepType` | Field in StepResultSummary |
| `calculation/runner.py:50-77` | `_coerce_step_type()` | Converts string → enum |
| `calculation/calculation.py:774-801` | `_coerce_step_type()` | Duplicate function |
| `calculation/verification.py:16-26` | `ENERGY_STEP_TYPES`, `FERMI_STEP_TYPES` | Sets for validation |
| `api.py:7757,7867` | `StepType.RELAX.value` | Value comparison |
| `cli/main.py:1746` | `StepType.from_string()` | **BUG**: Method doesn't exist! |

### 1.4 Persistence Analysis

**step.yaml stores strings, NOT enum values**:
```yaml
step_type: qe_scf  # machine_type string
```

**calculation.yaml stores strings**:
```yaml
steps:
  01ABCDEF: scf  # public_type string
```

**Evidence**: `step_factory.py:73` - `"step_type": machine_step_type`

**Conclusion**: ✅ Safe to delete - no persisted artifacts depend on enum.

### 1.5 Test Usage

| File | Usage |
|------|-------|
| `test_pyscf_integration.py:28-32` | `assert StepType.PYSCF_SCF.value == "pyscf_scf"` |
| `test_wannier90_integration.py:26-37` | Asserts enum values exist |
| `test_recipes.py` | Uses `StepType` for mock step creation (31 occurrences) |
| `test_gui_job_and_step_flows.py:687` | `step.step_type or StepType.CUSTOM` |
| `test_step_type_mapping.py:294-304` | Tests `_coerce_step_type()` |

### 1.6 Bug Found

**File**: `src/quantumvitas/cli/main.py:1746`
```python
step_type=StepType.from_string(spec.step_type) if spec.step_type else None,
```

`StepType.from_string()` doesn't exist! This is dead code or a latent bug.

---

## 2. Decision: Delete StepType Enum

**Why delete rather than isolate?**

1. Enum is NOT used for persistence (safe to remove)
2. Core logic already uses `StepTypeRegistry` for authoritative lookup
3. Mixed gen/spec values cause confusion
4. Keeping it creates technical debt and risks routing bugs
5. We control the entire codebase (no external compatibility needed)

---

## 3. Implementation Plan (PRs)

### PR0: Fix CLI Bug (from_string)

**Task**: Fix the non-existent `StepType.from_string()` call.

**Files**:
- [ ] `src/quantumvitas/cli/main.py` - line 1746

**Changes**:
```python
# Before (line 1746):
step_type=StepType.from_string(spec.step_type) if spec.step_type else None,

# After:
step_type=StepType(spec.step_type) if spec.step_type else None,
```

Or if spec.step_type might be a machine_type:
```python
step_type=_coerce_step_type(spec.step_type) if spec.step_type else None,
```

**Verification**:
```bash
pytest tests/unit/test_step_type_mapping.py -v -x
python -c "from quantumvitas.cli.main import *; print('CLI imports OK')"
```

**Tick checkboxes**: [ ] A. CLI bug fixed

---

### PR1: Replace StepType in Step and StepResultSummary with strings

**Task**: Change `step_type` fields from `StepType` to `Optional[str]`.

**Files**:
- [ ] `src/quantumvitas/calculation/step.py`
- [ ] `src/quantumvitas/calculation/results.py`
- [ ] `src/quantumvitas/calculation/__init__.py`

**Changes in step.py**:
```python
# Before (line 17):
from .types import StepMode, StepType

# After:
from .types import StepMode

# Before (line 29):
step_type: Optional[StepType] = None

# After:
step_type: Optional[str] = None
```

**Changes in results.py**:
```python
# Before (line 12):
from .types import StepMode, StepStatus, StepType

# After:
from .types import StepMode, StepStatus

# Before (line 18):
step_type: StepType

# After:
step_type: str
```

**Changes in __init__.py**:
```python
# Before (line 5):
from .types import StepMode, StepStatus, StepType

# After:
from .types import StepMode, StepStatus

# Update __all__ to remove "StepType"
```

**Verification**:
```bash
pytest tests/unit/test_workflow.py -v -x
pytest tests/unit/execution/test_recipes.py -v -x
python -c "from quantumvitas.calculation import Step; print(Step.__annotations__)"
```

**Tick checkboxes**: [ ] A. step.py updated, [ ] B. results.py updated, [ ] C. __init__.py updated

---

### PR2: Remove _coerce_step_type() and update callers

**Task**: Remove coercion functions and update callers to use strings directly.

**Files**:
- [ ] `src/quantumvitas/calculation/runner.py` - remove `_coerce_step_type()` (lines 50-77)
- [ ] `src/quantumvitas/calculation/calculation.py` - remove `_coerce_step_type()` (lines 774-801)
- [ ] Update all call sites to use string values

**Changes in runner.py**:

Remove function (lines 50-77) and update callers:
```python
# Before (line 593):
step_type = _coerce_step_type(step.step_type) if step.step_type else StepType.CUSTOM

# After:
step_type = step.step_type or "custom"

# Before (lines 232, 258):
step_type=StepType.CUSTOM,

# After:
step_type="custom",
```

**Changes in calculation.py**:

Remove function (lines 774-801) and update callers:
```python
# Before (lines 513, 523, 557):
step_type = StepType.CUSTOM
step_type=step_type or StepType.CUSTOM,

# After:
step_type = "custom"
step_type=step_type or "custom",
```

**Verification**:
```bash
pytest tests/unit/test_step_type_mapping.py::TestStepTypeMappingCompleteness -v -x
pytest tests/daemon/test_gui_job_and_step_flows.py -v -x
```

**Tick checkboxes**: [ ] A. runner.py coercion removed, [ ] B. calculation.py coercion removed

---

### PR3: Update verification.py to use string sets

**Task**: Replace StepType enum sets with string sets.

**File**:
- [ ] `src/quantumvitas/calculation/verification.py`

**Changes**:
```python
# Before (lines 11, 16-26):
from .types import StepMode, StepStatus, StepType

ENERGY_STEP_TYPES = {
    StepType.SCF,
    StepType.NSCF,
    StepType.DOS,
    StepType.BANDS_PW,
}
FERMI_STEP_TYPES = {
    StepType.NSCF,
    StepType.DOS,
    StepType.BANDS_PW,
}

# After:
from .types import StepMode, StepStatus

ENERGY_STEP_TYPES = {"scf", "nscf", "dos", "bands_pw"}
FERMI_STEP_TYPES = {"nscf", "dos", "bands_pw"}

# Update function signatures (lines 36, 85):
def strict_verify(step_type: str, ...
def evaluate_step_result(mode: StepMode, step_type: str, ...
```

**Verification**:
```bash
pytest tests/unit/test_step_type_mapping.py -v -x
python -c "from quantumvitas.calculation.verification import ENERGY_STEP_TYPES; print(ENERGY_STEP_TYPES)"
```

**Tick checkboxes**: [ ] A. verification.py updated to strings

---

### PR4: Update api.py to use string comparisons

**Task**: Replace `StepType.RELAX.value` with string literals.

**File**:
- [ ] `src/quantumvitas/api.py`

**Changes**:
```python
# Before (lines 7756-7757, 7866-7867):
from quantumvitas.calculation.types import StepType
if step_type not in (StepType.RELAX.value, StepType.VC_RELAX.value):

# After:
if step_type not in ("relax", "vc-relax"):
```

**Verification**:
```bash
python -c "from quantumvitas.api import QVService; print('API imports OK')"
```

**Tick checkboxes**: [ ] A. api.py updated

---

### PR5: Update CLI to use strings

**Task**: Remove StepType usage from CLI.

**File**:
- [ ] `src/quantumvitas/cli/main.py`

**Changes**:
```python
# Remove import (line 1668):
from quantumvitas.calculation.types import StepType

# Update Step construction (line 1746):
step_type=spec.step_type,  # Already a string from spec
```

**Verification**:
```bash
python -c "from quantumvitas.cli.main import *; print('CLI imports OK')"
```

**Tick checkboxes**: [ ] A. cli/main.py updated

---

### PR6: Delete StepType Enum and update tests

**Task**: Delete the enum definition and update all tests.

**Files**:
- [ ] `src/quantumvitas/calculation/types.py` - remove StepType class
- [ ] `tests/unit/test_pyscf_integration.py` - remove enum tests
- [ ] `tests/unit/test_wannier90_integration.py` - remove enum tests
- [ ] `tests/unit/execution/test_recipes.py` - use strings for mock steps
- [ ] `tests/daemon/test_gui_job_and_step_flows.py` - use string "custom"
- [ ] `tests/unit/test_step_type_mapping.py` - remove coerce_step_type test

**Changes in types.py**:
```python
# DELETE class StepType(str, Enum): ... (lines 10-30)
```

**Changes in test_pyscf_integration.py**:
```python
# DELETE test_pyscf_scf_in_step_type_enum() entirely
```

**Changes in test_wannier90_integration.py**:
```python
# DELETE enum tests (test_w90_preproc_in_step_type_enum, etc.)
```

**Changes in test_recipes.py**:
```python
# Before:
from quantumvitas.calculation.types import StepType
step_type: Optional[StepType]
def create_mock_step(ulid: str, step_type: StepType) -> MockStep:
steps = [create_mock_step("01ABCDEF", StepType.SCF)]

# After:
step_type: Optional[str]
def create_mock_step(ulid: str, step_type: str) -> MockStep:
steps = [create_mock_step("01ABCDEF", "scf")]
```

**Changes in test_gui_job_and_step_flows.py**:
```python
# Before:
step_type = step.step_type or StepType.CUSTOM

# After:
step_type = step.step_type or "custom"
```

**Changes in test_step_type_mapping.py**:
```python
# DELETE test_coerce_step_type_handles_spec() test
```

**Verification**:
```bash
pytest tests/unit/test_pyscf_integration.py -v -x
pytest tests/unit/test_wannier90_integration.py -v -x
pytest tests/unit/execution/test_recipes.py -v -x
pytest tests/daemon/test_gui_job_and_step_flows.py -v -x
pytest tests/unit/test_step_type_mapping.py -v -x
```

**Tick checkboxes**: [ ] A. types.py enum deleted, [ ] B. test_pyscf_integration.py updated, [ ] C. test_wannier90_integration.py updated, [ ] D. test_recipes.py updated, [ ] E. test_gui_job_and_step_flows.py updated, [ ] F. test_step_type_mapping.py updated

---

### PR7: Add guard tests (no StepType in production code)

**Task**: Add guard tests to prevent re-introduction of StepType.

**Create file**: `tests/unit/test_no_steptype_enum.py`

```python
"""
Guard test: Ensure StepType enum is not used in production code.

SSOT: Only gen/public step (string) and spec/machine step (string) are allowed.
"""

import subprocess
import pytest


def test_no_steptype_import_in_production():
    """Production code must not import StepType."""
    result = subprocess.run(
        ["rg", "-l", r"from.*StepType|import.*StepType", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    # Filter out types.py where StepMode/StepStatus are defined
    if matching_files:
        files = [f for f in matching_files.split('\n') if 'types.py' not in f]
        matching_files = '\n'.join(files)
    assert not matching_files, (
        f"Found StepType import in production code:\n{matching_files}\n\n"
        "SSOT violation: Use gen/public step (str) or spec/machine step (str) instead."
    )


def test_no_steptype_enum_definition():
    """StepType enum must not exist in types.py."""
    result = subprocess.run(
        ["rg", "-l", r"class StepType", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found StepType enum definition:\n{matching_files}\n\n"
        "SSOT violation: StepType enum must be deleted."
    )


def test_no_coerce_step_type_function():
    """_coerce_step_type must not exist."""
    result = subprocess.run(
        ["rg", "-l", r"def _coerce_step_type", "src/quantumvitas"],
        capture_output=True,
        text=True,
    )
    matching_files = result.stdout.strip()
    assert not matching_files, (
        f"Found _coerce_step_type function:\n{matching_files}\n\n"
        "This function is deprecated; use strings directly."
    )
```

**Verification**:
```bash
pytest tests/unit/test_no_steptype_enum.py -v
```

**Tick checkboxes**: [ ] A. Guard tests created and passing

---

## 4. Verification Commands (for evidence)

```bash
# Find all StepType imports
rg -l "from.*StepType|import.*StepType" src/quantumvitas

# Find all StepType usages
rg "StepType\." src/quantumvitas

# Find StepType in tests
rg "StepType" tests --stats

# Find _coerce_step_type
rg "def _coerce_step_type" src/quantumvitas

# Verify step.yaml format
cat tests/fixtures/*/step.yaml 2>/dev/null | head -20
```

---

## 5. Acceptance Criteria

After all PRs complete:

- [ ] 1. `StepType` enum is deleted from `types.py`
- [ ] 2. No production code imports `StepType`
- [ ] 3. `Step.step_type` is `Optional[str]`
- [ ] 4. `StepResultSummary.step_type` is `str`
- [ ] 5. `_coerce_step_type()` functions are deleted
- [ ] 6. `verification.py` uses string sets
- [ ] 7. Guard tests pass
- [ ] 8. All unit tests pass

---

## 6. Risk Register

| Risk | Trigger | Detection | Mitigation |
|------|---------|-----------|------------|
| Type safety regression | Step.step_type allows invalid strings | Tests fail on invalid step types | Add registry validation at creation |
| Comparison bugs | `step_type == "scf"` vs `step_type.value` | Unit tests | Comprehensive test coverage |
| Serialization change | Old code expects enum | step.yaml load fails | step.yaml already uses strings |
| Test breakage | Tests import StepType | pytest collection fails | Update tests in same PR |
| CLI dead code | from_string bug | Manual testing | Fix in PR0 |

---

## 7. Migration Notes

### String Value Mapping

When replacing StepType with strings, use lowercase values:

| Before | After |
|--------|-------|
| `StepType.SCF` | `"scf"` |
| `StepType.NSCF` | `"nscf"` |
| `StepType.CUSTOM` | `"custom"` |
| `StepType.RELAX` | `"relax"` |
| `StepType.VC_RELAX` | `"vc-relax"` |
| `StepType.PYSCF_SCF` | `"pyscf_scf"` |

### Validation Strategy

After deletion, step_type validation should happen at:
1. **Creation time**: `create_step_doc()` already validates via registry
2. **Load time**: Registry lookup validates machine_type
3. **Execution time**: Runner uses registry for engine resolution

---

## 8. Open Questions

1. **Should we add runtime validation for step_type strings?**
   - Recommendation: Yes, add `registry.validate_step_type(step_type)` at creation time

2. **Should Step.step_type store gen or spec?**
   - Current: Stores gen-like values (from coercion)
   - Recommendation: Store machine_type (spec) for consistency with step.yaml

