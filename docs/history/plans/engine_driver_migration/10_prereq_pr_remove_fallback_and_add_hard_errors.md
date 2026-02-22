# Prerequisite PR 1: Remove Fallbacks and Add Hard Errors

**PR Title**: `fix: Remove silent QE fallback and add hard errors for unknown types`

**Priority**: MUST complete before any engine migration

---

## 1. Objective

Remove all silent fallback behavior where unknown step types route to QE or any default engine. Replace with explicit hard errors that include helpful messages.

---

## 2. Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/qmatsuite/core/calc_identity.py` | Remove QE fallback in `_infer_engine_family_from_machine_types()` | HIGH |
| `src/qmatsuite/calculation/calculation.py` | Remove `.get("engine", "qe")` defaults | MEDIUM |
| `src/qmatsuite/execution/recipes.py` | Remove `QERecipe` fallback in `get_recipe_class()` | MEDIUM |
| `src/qmatsuite/core/driver_exceptions.py` | CREATE: Exception classes | LOW |
| `tests/gates/test_no_fallbacks.py` | CREATE: Gate 0 tests | LOW |

---

## 3. Step-by-Step Procedure

### Step 1: Create Exception Classes (Test First)

**Create file**: `src/qmatsuite/core/driver_exceptions.py`

```python
"""Exception classes for driver/routing errors."""

from typing import List, Optional


class DriverError(Exception):
    """Base class for driver-related errors."""
    pass


class UnknownStepTypeError(DriverError):
    """Raised when step type is not registered."""

    def __init__(self, step_type: str, known_types: Optional[List[str]] = None):
        self.step_type = step_type
        self.known_types = known_types or []
        similar = self._find_similar()

        msg = f"Step type '{step_type}' is not registered."
        if similar:
            msg += f"\nDid you mean: {', '.join(similar[:3])}?"
        if self.known_types:
            preview = sorted(self.known_types)[:20]
            msg += f"\nKnown types: {', '.join(preview)}"
            if len(self.known_types) > 20:
                msg += f"... ({len(self.known_types) - 20} more)"
        super().__init__(msg)

    def _find_similar(self, max_distance: int = 3) -> List[str]:
        """Find similar type names using Levenshtein distance."""
        if not self.known_types:
            return []

        def levenshtein(s1: str, s2: str) -> int:
            if len(s1) < len(s2):
                return levenshtein(s2, s1)
            if len(s2) == 0:
                return len(s1)
            prev_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                curr_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = prev_row[j + 1] + 1
                    deletions = curr_row[j] + 1
                    substitutions = prev_row[j] + (c1 != c2)
                    curr_row.append(min(insertions, deletions, substitutions))
                prev_row = curr_row
            return prev_row[-1]

        candidates = []
        for known in self.known_types:
            dist = levenshtein(self.step_type.lower(), known.lower())
            if dist <= max_distance:
                candidates.append((dist, known))

        candidates.sort(key=lambda x: x[0])
        return [c[1] for c in candidates]


class UnknownEngineError(DriverError):
    """Raised when engine family is not registered."""

    def __init__(self, engine: str, available: Optional[List[str]] = None):
        self.engine = engine
        self.available = available or []
        msg = f"No driver registered for engine '{engine}'."
        if self.available:
            msg += f"\nAvailable engines: {', '.join(sorted(self.available))}"
        super().__init__(msg)


class UnknownMaterializationError(DriverError):
    """Raised when GEN→SPEC mapping not found."""

    def __init__(
        self,
        engine: str,
        gen_type: str,
        known_gen_types: Optional[List[str]] = None,
    ):
        self.engine = engine
        self.gen_type = gen_type
        msg = f"No materialization for ({engine}, {gen_type})."
        if known_gen_types:
            msg += f"\nKnown generalized types for {engine}: {', '.join(known_gen_types)}"
        super().__init__(msg)
```

**Validation**: File compiles, exceptions can be instantiated

### Step 2: Write Gate 0 Tests (Must Fail Initially)

**Create file**: `tests/gates/__init__.py` (empty)

**Create file**: `tests/gates/test_no_fallbacks.py`

```python
"""Gate 0: No silent fallbacks tests.

These tests MUST FAIL before the fix and PASS after.
"""

import pytest
import re
from pathlib import Path


class TestNoSilentQEFallback:
    """Verify QE fallback removed from calc_identity.py."""

    def test_no_qe_fallback_pattern(self):
        """The specific QE fallback pattern must not exist."""
        source = Path("src/qmatsuite/core/calc_identity.py").read_text()

        # This exact pattern is the dangerous fallback
        # It should NOT be in the code after the fix
        dangerous_pattern = r'else:\s*\n\s*#.*\n\s*families\.add\("qe"\)'

        matches = re.findall(dangerous_pattern, source)
        assert len(matches) == 0, (
            "Silent QE fallback still exists in calc_identity.py.\n"
            "The pattern 'else: ... families.add(\"qe\")' must be removed."
        )

    def test_unknown_type_returns_none_not_qe(self):
        """Unknown type should return None, not 'qe'."""
        from qmatsuite.core.calc_identity import _infer_engine_family_from_machine_types

        result = _infer_engine_family_from_machine_types(["totally_unknown_xyz_123"])

        # After fix: should be None (not "qe")
        assert result is None, (
            f"Unknown step type returned '{result}' instead of None. "
            "Silent fallback still active."
        )


class TestNoDefaultEngineInCalculation:
    """Verify no .get('engine', 'qe') defaults."""

    def test_no_default_engine_qe_pattern(self):
        """No .get('engine', 'qe') in calculation loading."""
        source = Path("src/qmatsuite/calculation/calculation.py").read_text()

        pattern = r'\.get\(["\']engine["\'],\s*["\']qe["\']\)'
        matches = re.findall(pattern, source)

        assert len(matches) == 0, (
            f"Found {len(matches)} instances of .get('engine', 'qe') "
            "in calculation.py. These must be removed."
        )


class TestNoRecipeFallback:
    """Verify recipe selection has no QE fallback."""

    def test_no_qerecipe_default(self):
        """get_recipe_class should not default to QERecipe."""
        source = Path("src/qmatsuite/execution/recipes.py").read_text()

        # Pattern: .get(..., QERecipe) or default=QERecipe
        patterns = [
            r'\.get\([^)]+,\s*QERecipe\)',
            r'return.*QERecipe\s*#.*default',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, source)
            assert len(matches) == 0, (
                f"Found QERecipe fallback pattern in recipes.py"
            )
```

**Run tests**: `pytest tests/gates/test_no_fallbacks.py -v`

**Expected result**: Tests FAIL (this is correct - fixes not applied yet)

### Step 3: Fix calc_identity.py

**File**: `src/qmatsuite/core/calc_identity.py`

**Function**: `_infer_engine_family_from_machine_types()` (lines 78-115)

**Current code** (lines 96-108):
```python
    for machine_type in machine_types:
        if machine_type.startswith("qe_") or machine_type in ("w90_preproc", "w90_run"):
            families.add("qe")
        elif machine_type.startswith("pyscf_"):
            families.add("pyscf")
        elif machine_type.startswith("w90_"):
            families.add("w90")
        else:
            # Unknown prefix - could be legacy step type
            # Assume QE for backward compatibility
            families.add("qe")
```

**Replace with**:
```python
    for machine_type in machine_types:
        if machine_type.startswith("qe_") or machine_type in ("w90_preproc", "w90_run"):
            families.add("qe")
        elif machine_type.startswith("pyscf_"):
            families.add("pyscf")
        elif machine_type.startswith("w90_"):
            families.add("w90")
        elif machine_type.startswith("vasp_"):
            families.add("vasp")
        elif machine_type.startswith("orca_"):
            families.add("orca")
        elif machine_type.startswith("lammps_"):
            families.add("lammps")
        elif machine_type.startswith("cp2k_"):
            families.add("cp2k")
        # else: Unknown type - do NOT add to families
        # Return None below if no families identified
```

**Also update the return logic** (after the loop):
```python
    # Return single family if all steps belong to one family
    if len(families) == 1:
        return families.pop()

    # Mixed families or no recognized families - return None
    # Caller must handle None appropriately (not assume QE)
    return None
```

**Validation**: `test_no_qe_fallback_pattern` passes

### Step 4: Fix calculation.py

**File**: `src/qmatsuite/calculation/calculation.py`

**Find via ripgrep**: `rg '\.get\("engine", "qe"\)' src/qmatsuite/calculation/`

**Line 339** (approximate - verify with ripgrep):
```python
# BEFORE:
engine_name = step_data.get("engine", "qe")

# AFTER:
engine_name = step_data.get("engine")
if engine_name is None:
    # Engine must be specified or inferred from step type
    step_type = step_data.get("type") or step_data.get("step_type")
    if step_type:
        from qmatsuite.workflow.registry import get_registry
        registry = get_registry()
        spec = registry.get(step_type)
        if spec:
            engine_name = spec.engine
    if engine_name is None:
        raise ValueError(
            f"Cannot determine engine for step. "
            f"Specify 'engine' field or use a known step type."
        )
```

**Line 455** (approximate - verify with ripgrep):
```python
# Same pattern - apply same fix
```

**Validation**: `test_no_default_engine_qe_pattern` passes

### Step 5: Fix recipes.py

**File**: `src/qmatsuite/execution/recipes.py`

**Find via ripgrep**: `rg 'QERecipe' src/qmatsuite/execution/recipes.py`

**Function `get_recipe_class()`** (around line 798-827):
```python
# BEFORE:
def get_recipe_class(engine_family: str) -> type[BaseRecipe]:
    recipe_map = {
        "qe": QERecipe,
        "orca": ORCARecipe,
        # ...
    }
    return recipe_map.get(engine_family, QERecipe)  # DANGEROUS

# AFTER:
def get_recipe_class(engine_family: str) -> type[BaseRecipe]:
    recipe_map = {
        "qe": QERecipe,
        "orca": ORCARecipe,
        "pyscf": PySCFRecipe,
        "vasp": VASPRecipe,
        "lammps": LAMMPSRecipe,
        "cp2k": CP2KRecipe,
    }
    if engine_family not in recipe_map:
        from qmatsuite.core.driver_exceptions import UnknownEngineError
        raise UnknownEngineError(engine_family, list(recipe_map.keys()))
    return recipe_map[engine_family]
```

**Validation**: `test_no_qerecipe_default` passes

### Step 6: Run All Gate 0 Tests

```bash
pytest tests/gates/test_no_fallbacks.py -v
```

**Expected**: All tests PASS

### Step 7: Run Full Test Suite

```bash
pytest tests/ -v
```

**Expected**: All existing tests pass. If any fail:
1. Identify if they relied on fallback behavior
2. Fix test to specify engine explicitly
3. Document the fix

---

## 4. Tests to Add (Summary)

| Test File | Test | Purpose |
|-----------|------|---------|
| `tests/gates/test_no_fallbacks.py` | `test_no_qe_fallback_pattern` | Static check for QE fallback |
| `tests/gates/test_no_fallbacks.py` | `test_unknown_type_returns_none_not_qe` | Runtime check |
| `tests/gates/test_no_fallbacks.py` | `test_no_default_engine_qe_pattern` | Static check |
| `tests/gates/test_no_fallbacks.py` | `test_no_qerecipe_default` | Static check |
| `tests/core/test_driver_exceptions.py` | `test_unknown_step_type_error_message` | Error formatting |
| `tests/core/test_driver_exceptions.py` | `test_unknown_step_type_suggestions` | Levenshtein suggestions |

---

## 5. Expected Behavior Changes

| Before | After | Impact |
|--------|-------|--------|
| Unknown step type → QE | Unknown step type → None/Error | Explicit failure |
| Missing engine → "qe" | Missing engine → Error | Must specify engine |
| Unknown recipe → QERecipe | Unknown recipe → UnknownEngineError | Explicit failure |

**User-facing impact**: Calculations with typos or missing engine specs will now fail explicitly instead of silently running as QE.

---

## 6. Rollback Strategy

If critical issues discovered after merge:

1. Revert the commit: `git revert <commit-hash>`
2. The original fallback behavior is restored
3. Add logging to track fallback usage before re-attempting

---

## 7. PR Checklist

- [ ] `driver_exceptions.py` created with all exception classes
- [ ] `tests/gates/test_no_fallbacks.py` created
- [ ] Gate 0 tests pass
- [ ] `calc_identity.py` QE fallback removed
- [ ] `calculation.py` default engine removed
- [ ] `recipes.py` QERecipe fallback removed
- [ ] Full test suite passes
- [ ] No regressions in CI

---

## 8. Definition of Done

1. All Gate 0 tests pass
2. No `.get("engine", "qe")` patterns in codebase
3. No silent `families.add("qe")` fallback
4. Unknown types raise `UnknownStepTypeError` or return `None`
5. Recipe dispatch raises `UnknownEngineError` for unknown engines
6. All existing tests pass
7. CI green
