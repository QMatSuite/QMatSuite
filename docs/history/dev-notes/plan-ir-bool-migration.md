# Plan: IR Boolean Migration

**Status**: Ready for implementation  
**Created**: 2026-01-17  
**Spec**: `docs/dev/spec-ir-bool-canonicalization.md`

---

## 1. Code Inventory

### 1.1 Production Code with `.true.`/`.false.` Strings

| File | Lines | Issue |
|------|-------|-------|
| `src/qmatsuite/presets/paramspace.py` | 601-605 | `compile_profile_patch()` converts bool → `.true.`/`.false.` via `ir_bool()` |
| `src/qmatsuite/presets/paramspace.py` | 619-636 | `parse_bool()` parses `.true.`/`.false.` strings |
| `src/qmatsuite/ir/backends/qe/mapping.py` | 14-41 | `ir_bool()` function returns `.true.`/`.false.` strings |
| `src/qmatsuite/ir/backends/qe/mapping.py` | 118-122 | `ir_to_qe_param()` converts bool to `.true.`/`.false.` |
| `src/qmatsuite/ir/backends/qe/mapping.py` | 156-180 | `_normalize_qe_value_to_ir()` parses `.true.`/`.false.` (CORRECT - import boundary) |
| `src/qmatsuite/presets/detector.py` | 68-83 | `_parse_bool()` parses `.true.`/`.false.` (CORRECT - robustness) |
| `src/qmatsuite/presets/integration.py` | 44-52 | `_strict_parse_bool_value()` parses `.true.`/`.false.` |
| `src/qmatsuite/presets/integration.py` | 813 | Comment references QE format in step.yaml (needs update) |
| `src/qmatsuite/cli/main.py` | 299-302, 555-558 | CLI parsing `.true.`/`.false.` from user input (CORRECT - user boundary) |
| `src/qmatsuite/io/parser/qe_parser.py` | 72-75 | QE parser converts `.true.`/`.false.` → bool (CORRECT - import boundary) |
| `src/qmatsuite/io/generator/qe_generator.py` | 21-22 | QE writer converts bool → `.true.`/`.false.` (CORRECT - export boundary) |

### 1.2 Test Files with `.true.`/`.false.` Strings

| File | Count | Fix |
|------|-------|-----|
| `tests/unit/test_magnetism_paramspace_contract.py` | 13 | Update test dicts and assertions |
| `tests/unit/test_preset_integration.py` | 2 | Update assertions |
| `tests/unit/test_detector_b.py` | 5 | Update test dicts and assertions |
| `tests/integration/test_preset_broadcast.py` | 3 | Update test dicts |
| `tests/unit/test_ir_dialect_structure.py` | ? | Check and update |
| `tests/unit/test_qc_precision_paramspace.py` | ? | Check and update |
| `tests/unit/test_wannier90_integration.py` | ? | Check and update |

### 1.3 Data Files with `.true.`/`.false.`

| File | Type | Action |
|------|------|--------|
| `tests/data/*.in` files | QE input files | No change needed (QE format) |
| `tests/data/*.yaml` files | Step/calc YAML | Check for strings, should be booleans |
| `src/qmatsuite/data/*.json` | UI parameters | Check for `.true.` strings |

---

## 2. Migration Strategy

### 2.1 Order of Changes

1. **PR0**: Remove bool→string conversion in ParamSpace (core fix)
2. **PR1**: Remove bool→string conversion in IR mapping
3. **PR2**: Update unit tests to expect Python bool
4. **PR3**: Update integration tests
5. **PR4**: Add guard tests
6. **PR5**: Final verification

### 2.2 Key Insight

The QE generator (`qe_generator.py`) already correctly converts `bool` → `.true.` at output time. The problem is we're converting too early (in ParamSpace), storing strings in YAML, then the generator doesn't see bools.

Fix: Keep booleans as Python `bool` until the very last moment (QE `.in` generation).

---

## 3. Implementation Plan

### PR0: Remove bool→string conversion in ParamSpace
- [x] Modify `src/qmatsuite/presets/paramspace.py:compile_profile_patch()`:
  - Remove lines 601-605 that call `ir_bool()`
  - Boolean values stay as Python `bool`
- [x] Update comment at line 601 to reflect new contract

**Files to modify**:
- `src/qmatsuite/presets/paramspace.py`

**Tests to run**:
```bash
pytest tests/presets/test_paramspace_ir.py -v -x
```

**Expected**: Tests may fail because they expect `.true.` strings. This is expected; we fix tests in PR2.

---

### PR1: Remove bool→string conversion in IR mapping
- [x] Delete `ir_bool()` function from `src/qmatsuite/ir/backends/qe/mapping.py`
- [x] Modify `ir_to_qe_param()`:
  - Remove lines 118-122 that convert bool to `.true.`/`.false.`
  - Return Python `bool` as-is
- [x] Update `ir_params_to_qe_params()` to NOT convert booleans
- [x] Update comment about serialization to clarify QE writer handles it
- [x] Remove `ir_bool` import from `src/qmatsuite/ir/dialects/pw/__init__.py`

**Files to modify**:
- `src/qmatsuite/ir/backends/qe/mapping.py`
- `src/qmatsuite/ir/dialects/pw/__init__.py`

**Tests to run**:
```bash
pytest tests/ir/ -v -x
```

---

### PR2: Update unit tests to expect Python bool
- [x] Update `tests/unit/test_magnetism_paramspace_contract.py`:
  - Change all `.true.`/`.false.` strings in test dicts to Python `True`/`False`
  - Update assertions to expect `bool` instead of strings
- [x] Update `tests/unit/test_detector_b.py`:
  - Input dicts can still use `.true.` (testing robustness)
  - Output assertions must expect `bool`
- [x] Update `tests/unit/test_preset_integration.py`:
  - Change assertions to expect `bool`
- [x] Update `tests/unit/test_ir_dialect_structure.py`:
  - Check for `.true.` strings and update
- [x] Update `tests/unit/test_qc_precision_paramspace.py`:
  - Check for `.true.` strings and update

**Files to modify**:
- `tests/unit/test_magnetism_paramspace_contract.py`
- `tests/unit/test_detector_b.py`
- `tests/unit/test_preset_integration.py`
- `tests/unit/test_ir_dialect_structure.py`
- `tests/unit/test_qc_precision_paramspace.py`

**Tests to run**:
```bash
pytest tests/unit/test_magnetism_paramspace_contract.py -v
pytest tests/unit/test_detector_b.py -v
pytest tests/unit/test_preset_integration.py -v
pytest tests/unit/test_ir_dialect_structure.py -v
pytest tests/unit/test_qc_precision_paramspace.py -v
```

---

### PR3: Update integration tests
- [x] Update `tests/integration/test_preset_broadcast.py`:
  - Change all `.true.`/`.false.` strings to Python `bool`
- [x] Update `tests/presets/test_integration_ir.py` (if needed)
- [x] Update any other integration tests with `.true.` strings

**Files to modify**:
- `tests/integration/test_preset_broadcast.py`
- `tests/presets/test_integration_ir.py` (if needed)

**Tests to run**:
```bash
pytest tests/integration/test_preset_broadcast.py -v
pytest tests/presets/ -v
```

---

### PR4: Add guard tests
- [x] Create `tests/unit/test_no_qe_bool_strings.py` with:
  - `test_ir_patch_has_no_qe_bool_strings`: Compile each ParamSpace profile, scan output for `.true.`/`.false.` strings
  - `test_yaml_loader_rejects_qe_bool_strings`: Loading YAML with `.true.` string should work but guard should catch it
  - `test_qe_output_has_fortran_bools`: QE generator outputs `.true.`/`.false.` correctly
- [x] Add scanner helper function to recursively check dicts for forbidden strings

**Files to create**:
- `tests/unit/test_no_qe_bool_strings.py`

**Tests to run**:
```bash
pytest tests/unit/test_no_qe_bool_strings.py -v
```

---

### PR5: Final verification and cleanup
- [x] Run full test suite
- [x] Remove deprecated `parse_bool()` from `paramspace.py` or mark as internal
- [x] Update `integration.py` comment at line 813
- [x] Verify all step.yaml files in test data use YAML booleans

**Tests to run**:
```bash
pytest tests/unit/ tests/presets/ tests/integration/ -v --tb=short
```

---

## 4. Implementation Log

_Auto will update this section as PRs are implemented._

```
PR0: [x] Remove bool→string conversion in ParamSpace
PR1: [x] Remove bool→string conversion in IR mapping
PR2: [x] Update unit tests to expect Python bool
PR3: [x] Update integration tests
PR4: [x] Add guard tests
PR5: [x] Final verification and cleanup
```

---

## 5. Acceptance Criteria

- [x] No `.true.`/`.false.` strings in IR patches (verified by guard test)
- [x] step.yaml stores YAML native `true`/`false` (verified by guard test)
- [x] QE `.in` output contains `.true.`/`.false.` (verified by guard test)
- [x] All existing tests pass after migration
- [x] New guard tests prevent regression

---

## 6. Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking YAML files that already have `.true.` strings | Spec says hard error; regenerate any affected fixtures |
| QE writer not seeing booleans | Already handles `bool` correctly |
| Detection failing on clean YAML | Detection `_parse_bool()` still handles both (robustness) |
| Large number of test updates | PRs are incremental; fix test files one by one |

---

## 7. Prompts for Cursor Auto

### PR0 Prompt

```
You are AUTO implementing PR0 from docs/dev/plan-ir-bool-migration.md

TASK: Remove bool→string conversion in ParamSpace.

MODIFY: src/qmatsuite/presets/paramspace.py

CHANGES:
1. At lines 601-606, REMOVE the following code block:
   # Convert boolean values to IR canonical format (.true./.false.)
   # IR contract: boolean values must be canonical strings, not Python bool
   if isinstance(value, bool):
       from qmatsuite.ir.backends.qe.mapping import ir_bool
       value = ir_bool(value)

2. Replace with comment:
   # Boolean values stay as Python bool (YAML canonical)
   # QE writer converts to .true./.false. at output boundary

VERIFICATION:
python -c "from qmatsuite.presets.paramspace import compile_profile_patch; print('Import OK')"

TICK CHECKBOX: PR0 in plan file section 4
COMMIT: "ParamSpace: keep booleans as Python bool, not .true. strings (PR0)"
STOP IF: Import errors. Do not run full tests yet (tests will fail until PR2).
```

### PR1 Prompt

```
You are AUTO implementing PR1 from docs/dev/plan-ir-bool-migration.md

TASK: Remove bool→string conversion in IR mapping.

MODIFY: src/qmatsuite/ir/backends/qe/mapping.py

CHANGES:
1. DELETE the ir_bool() function (lines 14-41)

2. In ir_to_qe_param() (around lines 114-124), REMOVE:
   # Convert Python bool to QE string format for boolean parameters
   if isinstance(ir_value, bool):
       # QE boolean parameters that must use string format
       boolean_params = {"noncolin", "lspinorb", "nosym", "noinv"}
       if qe_key in boolean_params:
           qe_value = ".true." if ir_value else ".false."

3. Update docstring for ir_to_qe_param to clarify: 
   "Boolean values remain as Python bool. QE writer converts at output."

4. In ir_params_to_qe_params(), ensure booleans pass through unchanged

MODIFY: src/qmatsuite/ir/dialects/pw/__init__.py

CHANGES:
1. Remove ir_bool from imports if present

VERIFICATION:
python -c "from qmatsuite.ir.backends.qe.mapping import ir_to_qe_param; print('Import OK')"

TICK CHECKBOX: PR1 in plan file section 4
COMMIT: "IR mapping: keep booleans as Python bool (PR1)"
STOP IF: Import errors.
```

### PR2 Prompt

```
You are AUTO implementing PR2 from docs/dev/plan-ir-bool-migration.md

TASK: Update unit tests to expect Python bool.

MODIFY: tests/unit/test_magnetism_paramspace_contract.py
- Replace ".true." with True
- Replace ".false." with False
- Update assertions: system.get("noncolin") == True (not ".true.")

MODIFY: tests/unit/test_detector_b.py
- For detection INPUT dicts: can keep ".true." (testing robustness)
- For compilation OUTPUT assertions: change to True/False

MODIFY: tests/unit/test_preset_integration.py
- Update assertions to expect bool

MODIFY: tests/unit/test_ir_dialect_structure.py
- Check for and update any ".true." strings

MODIFY: tests/unit/test_qc_precision_paramspace.py
- Check for and update any ".true." strings

VERIFICATION:
pytest tests/unit/test_magnetism_paramspace_contract.py -v
pytest tests/unit/test_detector_b.py -v
pytest tests/unit/test_preset_integration.py -v

TICK CHECKBOX: PR2 in plan file section 4
COMMIT: "Tests: update unit tests to expect Python bool (PR2)"
```

### PR3 Prompt

```
You are AUTO implementing PR3 from docs/dev/plan-ir-bool-migration.md

TASK: Update integration tests.

MODIFY: tests/integration/test_preset_broadcast.py
- Replace ".true." with True
- Replace ".false." with False

MODIFY: tests/presets/test_integration_ir.py (if it has .true. strings)
- Update similarly

VERIFICATION:
pytest tests/integration/test_preset_broadcast.py -v
pytest tests/presets/ -v

TICK CHECKBOX: PR3 in plan file section 4
COMMIT: "Tests: update integration tests to expect Python bool (PR3)"
```

### PR4 Prompt

```
You are AUTO implementing PR4 from docs/dev/plan-ir-bool-migration.md

TASK: Add guard tests.

CREATE: tests/unit/test_no_qe_bool_strings.py

Content must include:

```python
"""
Guard tests to prevent .true./.false. strings in IR/YAML.

Per spec-ir-bool-canonicalization.md:
- IR patches must use Python bool
- YAML must store native true/false
- Only QE .in output should have .true./.false.
"""

import pytest

def _scan_for_qe_bool_strings(obj, path=""):
    """Recursively scan dict/list for .true./.false. strings."""
    forbidden = {".true.", ".false."}
    errors = []
    
    if isinstance(obj, dict):
        for k, v in obj.items():
            errors.extend(_scan_for_qe_bool_strings(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errors.extend(_scan_for_qe_bool_strings(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        if obj.lower().strip() in forbidden:
            errors.append(f"{path}: found forbidden string {obj!r}")
    
    return errors


class TestIRPatchHasNoBoolStrings:
    """IR patches from ParamSpace must not contain .true./.false. strings."""
    
    def test_magnetism_profiles_use_python_bool(self):
        from qmatsuite.presets.paramspace import (
            get_magnetism_paramspace,
            compile_profile_patch,
        )
        space = get_magnetism_paramspace()
        for profile_name in space.profiles:
            patch, _ = compile_profile_patch(space, profile_name)
            errors = _scan_for_qe_bool_strings(patch)
            assert not errors, f"Profile {profile_name}: {errors}"
    
    def test_precision_profiles_use_python_bool(self):
        from qmatsuite.presets.precision_variants import build_precision_pw_default_space
        from qmatsuite.presets.paramspace import compile_profile_patch
        space = build_precision_pw_default_space()
        for profile_name in space.profiles:
            patch, _ = compile_profile_patch(space, profile_name)
            errors = _scan_for_qe_bool_strings(patch)
            assert not errors, f"Profile {profile_name}: {errors}"


class TestQEOutputHasFortranBools:
    """QE .in output must use .true./.false. for booleans."""
    
    def test_qe_generator_converts_bool_to_fortran(self):
        from qmatsuite.io.generator.qe_generator import QEInputGenerator
        
        assert QEInputGenerator.format_value(True) == ".true."
        assert QEInputGenerator.format_value(False) == ".false."
```

VERIFICATION:
pytest tests/unit/test_no_qe_bool_strings.py -v

TICK CHECKBOX: PR4 in plan file section 4
COMMIT: "Tests: add guard tests for bool representation (PR4)"
```

### PR5 Prompt

```
You are AUTO implementing PR5 from docs/dev/plan-ir-bool-migration.md

TASK: Final verification and cleanup.

OPTIONAL CLEANUP:
1. In src/qmatsuite/presets/integration.py, update comment at line 813:
   - Remove reference to "QE: .true./.false."
   - Clarify that step.yaml stores Python bool

2. In src/qmatsuite/presets/paramspace.py:
   - Consider marking parse_bool() as internal-only (add underscore: _parse_bool)

VERIFICATION:
pytest tests/unit/ tests/presets/ tests/integration/ -v --tb=short -n auto

TICK ALL CHECKBOXES in plan file section 4
TICK ALL CHECKBOXES in Acceptance Criteria section 5
COMMIT: "Bool migration: final cleanup and verification (PR5)"
```

---

## 8. Appendix: Ripgrep Commands Used

```bash
# Find all .true./.false. in production code
rg '\.true\.|\.false\.' src/qmatsuite --type py

# Find all .true./.false. in tests
rg '\.true\.|\.false\.' tests --type py

# Find ir_bool usages
rg 'ir_bool' src/qmatsuite --type py

# Check YAML files for string booleans
rg '\.true\.|\.false\.' --glob '*.yaml' --glob '*.yml'
```

