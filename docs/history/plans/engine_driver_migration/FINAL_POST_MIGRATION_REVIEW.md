# Final Post-Migration Review: Engine Driver Migration

**Version**: 1.0
**Date**: 2026-01-21
**Status**: POST-MIGRATION COMPLIANCE AUDIT
**Auditor**: Claude Opus 4.5

---

## Executive Summary

The engine driver migration has been **largely completed** with driver bundles properly structured and registered. However, **2 CRITICAL violations** and **3 HIGH/MEDIUM issues** remain that violate the kernel-driver separation contract.

| Category | Status |
|----------|--------|
| DriverRegistry Implementation | ✅ COMPLIANT |
| Driver Bundle Structure (7 engines) | ✅ COMPLIANT |
| Error Classes | ✅ COMPLIANT |
| No QE Fallbacks | ❌ 2 VIOLATIONS FOUND |
| No startswith() Patterns | ❌ 1 VIOLATION FOUND |
| No Hardcoded Engine Lists | ⚠️ 2 ISSUES FOUND |
| Test Gates | ✅ PRESENT |

---

## A. DriverRegistry Compliance

### Status: ✅ FULLY COMPLIANT

**Evidence**: `src/quantumvitas/core/driver_registry.py`

The DriverRegistry implementation fully conforms to spec:

| Requirement | Implementation | Lines |
|-------------|----------------|-------|
| Singleton pattern | `__new__` with `_lock` | 57-63 |
| `register()` validation | `_validate_driver()` | 97-133 |
| `get_driver()` with hard error | `UnknownEngineError` | 180-195 |
| `get_handler()` with hard error | `UnknownStepTypeError` | 197-216 |
| `get_step_type_spec()` with hard error | `UnknownStepTypeError` | 234-250 |
| `materialize_step_type()` with hard error | `UnknownMaterializationError` | 270-296 |
| Version compatibility check | API version validation | 160-165 |
| Duplicate engine rejection | `DuplicateEngineError` | 108-111 |
| Duplicate step type rejection | `DuplicateStepTypeError` | 119-123 |

**Error Classes** (`src/quantumvitas/core/driver_exceptions.py`):
- `UnknownStepTypeError` with Levenshtein suggestions: ✅ Lines 11-57
- `UnknownEngineError` with available engines: ✅ Lines 60-69
- `UnknownMaterializationError`: ✅ Lines 72-86
- `DuplicateEngineError`, `DuplicateStepTypeError`: ✅ Lines 94-101

---

## B. Driver Bundle Compliance

### Status: ✅ ALL 7 DRIVERS COMPLIANT

| Engine | Location | Registration | MUST Items |
|--------|----------|--------------|------------|
| QE | `drivers/qe/` | ✅ Line 12 | ✅ All 7 |
| VASP | `drivers/vasp/` | ✅ Line 12 | ✅ All 7 |
| ORCA | `drivers/orca/` | ✅ Line 12 | ✅ All 7 |
| PySCF | `drivers/pyscf/` | ✅ Line 12 | ✅ All 7 |
| LAMMPS | `drivers/lammps/` | ✅ Line 12 | ✅ All 7 |
| CP2K | `drivers/cp2k/` | ✅ Line 12 | ✅ All 7 |
| W90 | `drivers/w90/` | ✅ Line 15 | ✅ All 7 |

**Evidence** (VASP driver as example): `src/quantumvitas/drivers/vasp/driver.py`

```python
# Lines 26-36: MUST properties
@property def engine_family(self) -> str: return "vasp"
@property def display_name(self) -> str: return "VASP"
@property def driver_api_version(self) -> str: return "1.0.0"

# Lines 42-148: MUST methods
def get_step_type_specs(self) -> list[StepTypeSpec]: ...  # 11 step types
def get_handler(self): from .handler import vasp_step_handler; return vasp_step_handler
def get_recipe_class(self): from .recipe import VASPRecipe; return VASPRecipe
def get_materialization_map(self) -> dict[str, str]: ...  # 5 mappings
```

**Auto-registration** (`src/quantumvitas/drivers/__init__.py`):
- All 7 drivers imported at lines 21-39
- Each `__init__.py` calls `DriverRegistry.register()` on import

---

## C. CRITICAL VIOLATIONS: Silent Fallbacks

### VIOLATION C1: QE Fallback in `models.py`

**Severity**: 🔴 CRITICAL
**Location**: `src/quantumvitas/core/models.py:35-95`
**Function**: `_infer_engine_family_from_steps()`

```python
# Lines 55-67: Hardcoded QE step types
qe_types = {"scf", "nscf", "relax", "vc-relax", ...}
for step_type in qe_types:
    step_type_to_family[step_type] = "qe"

# Lines 68-71: W90 hardcoded as QE family
w90_types = {"w90_preproc", "w90_run"}
for step_type in w90_types:
    step_type_to_family[step_type] = "qe"  # VIOLATION

# Lines 86-88: Silent QE fallback
elif not step_type.startswith(("qe_", "w90_", "pyscf_")):
    # Legacy step type without prefix - assume QE
    families.add("qe")  # ← CRITICAL VIOLATION
```

**Impact**: Unknown step types silently route to QE instead of raising an error.

---

### VIOLATION C2: QE Fallback in `handlers.py`

**Severity**: 🔴 CRITICAL
**Location**: `src/quantumvitas/execution/handlers.py:220-230`
**Function**: `create_handler_map()`

```python
# Lines 220-226: Exception handler falls back to QE
except Exception as e:
    logger.warning(f"Could not register handler for {engine}: {e}")
    # Fallback to legacy handlers for engines not yet migrated
    if engine == "qe":
        handler_map["qe"] = make_handler(qe_step_handler)  # ← VIOLATION

# Lines 228-230: Legacy QE always-available fallback
if "qe" not in handler_map:
    handler_map["qe"] = make_handler(qe_step_handler)  # ← VIOLATION
```

**Impact**: QE handler is always injected regardless of registry state.

---

## D. HIGH VIOLATIONS: Engine Detection Patterns

### VIOLATION D1: startswith() Patterns in `generalized_steps.py`

**Severity**: 🟠 HIGH
**Location**: `src/quantumvitas/workflow/generalized_steps.py:372-414`
**Function**: `get_generalized_step_from_engine_specific()`

```python
# Lines 372-391: QE prefix detection
if engine_specific_step.startswith("qe_"):
    engine_family = "qe"
    step_name = engine_specific_step[3:]  # Prefix stripping
    step_to_generalized = {...}

# Lines 392-395: W90 hardcoded as QE
elif engine_specific_step.startswith("w90_"):
    engine_family = "qe"  # ← VIOLATION: W90 is separate engine now

# Lines 396-406: Other prefixes
elif engine_specific_step.startswith("pyscf_"):
    engine_family = "pyscf"
elif engine_specific_step.startswith("orca_"):
    engine_family = "orca"
```

**Impact**: Bypasses registry for engine detection; won't work with new engines.

---

### VIOLATION D2: W90-QE Coupling in `generalized_steps.py`

**Severity**: 🟠 HIGH
**Location**: `src/quantumvitas/workflow/generalized_steps.py:286`

```python
# Line 286: Special case for w90
if spec_engine_family == "qe" and engine_family == "qe" and spec.machine_type.startswith("w90_"):
    return spec.machine_type  # ← Assumes W90 is part of QE
```

**Impact**: W90 is now a separate driver but this code assumes it's part of QE.

---

## E. MEDIUM ISSUES: Hardcoded Engine Lists

### ISSUE E1: Hardcoded Engine List in `calculation.py`

**Severity**: 🟡 MEDIUM
**Location**: `src/quantumvitas/calculation/calculation.py:396, 555`

```python
# Lines 396, 555 (duplicated code)
for engine_family in ["qe", "vasp", "orca", "pyscf", "cp2k", "lammps", "w90"]:
    try:
        materialized = DriverRegistry.materialize_step_type(engine_family, ...)
```

**Impact**: New engines must be manually added to this list.
**Fix**: Use `DriverRegistry.get_all_engines()` instead.

---

## F. Compliant Components

### F1: calc_identity.py `_infer_engine_family_from_machine_types()`

**Status**: ✅ COMPLIANT
**Location**: `src/quantumvitas/core/calc_identity.py:79-111`

```python
# Uses registry correctly
if DriverRegistry.is_step_type_registered(step_type):
    engine = DriverRegistry.get_engine_for_step_type(step_type)
    families.add(engine)
# Unknown step types are ignored - will fail at handler dispatch
```

### F2: recipes.py `get_recipe_for_engine()`

**Status**: ✅ COMPLIANT
**Location**: `src/quantumvitas/execution/recipes.py:237-254`

```python
def get_recipe_for_engine(engine_family: str) -> BaseRecipe:
    import quantumvitas.drivers
    recipe_class = DriverRegistry.get_recipe_class(engine_family)  # Hard error
    return recipe_class()
```

### F3: Test Gates

**Status**: ✅ PRESENT
**Location**: `tests/gates/`

| Test File | Coverage |
|-----------|----------|
| `test_no_fallbacks.py` | Gate 0: Silent fallback detection |
| `test_registry_routing.py` | Gate 1: Registry-based routing |

---

## G. Test Gate Results

Based on current code state, the following test failures are expected:

| Test | Expected Result | Actual Issue |
|------|-----------------|--------------|
| `test_no_qe_fallback_pattern` | ❌ FAIL | `models.py:88` has `families.add("qe")` |
| `test_unknown_type_returns_none_not_qe` | ⚠️ UNCLEAR | `_infer_engine_family_from_machine_types` is compliant, but `_infer_engine_family_from_steps` is not |
| `test_no_default_engine_qe_pattern` | ✅ PASS | No `.get('engine', 'qe')` patterns found |
| `test_no_qerecipe_default` | ✅ PASS | No QERecipe fallback in `get_recipe_for_engine` |

---

## Summary: Required Fixes

| Priority | File | Issue | Lines |
|----------|------|-------|-------|
| 🔴 CRITICAL | `core/models.py` | QE fallback for legacy step types | 86-88 |
| 🔴 CRITICAL | `execution/handlers.py` | QE handler fallback | 220-230 |
| 🟠 HIGH | `workflow/generalized_steps.py` | startswith() engine detection | 372-414 |
| 🟠 HIGH | `workflow/generalized_steps.py` | W90-QE coupling | 286, 392-395 |
| 🟡 MEDIUM | `calculation/calculation.py` | Hardcoded engine list | 396, 555 |
| 🟡 MEDIUM | `core/models.py` | Hardcoded QE/W90 step types | 55-71 |

---

## Recommendation

**Migration Status**: 90% Complete

The driver bundle architecture is correctly implemented. The remaining issues are legacy fallback patterns that were not removed during migration. These must be fixed to achieve the kernel-driver separation goal.

See `FINAL_AUTOFIX_PLAN.md` for the specific code changes required.
