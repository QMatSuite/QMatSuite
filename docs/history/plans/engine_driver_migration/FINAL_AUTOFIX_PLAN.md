# Final Autofix Plan: Engine Driver Migration

**Version**: 1.0
**Date**: 2026-01-21
**Status**: AUTOFIX SPECIFICATION
**For**: Cursor Auto / Claude Code

---

## Overview

This document specifies the exact code changes needed to complete the engine driver migration.
Each fix is atomic and can be applied independently. All fixes together bring the codebase
to 100% compliance with the kernel-driver separation contract.

**Total Fixes**: 5 (2 Critical, 2 High, 1 Medium)

---

## Fix 1: Remove QE Fallback in `models.py` [CRITICAL]

**File**: `src/quantumvitas/core/models.py`
**Function**: `_infer_engine_family_from_steps()`
**Lines**: 35-95 (entire function)

### Current Code (BROKEN)

```python
def _infer_engine_family_from_steps(steps: List["CalculationStepEntry"]) -> Optional[str]:
    """..."""
    if not steps:
        return None

    # Map step types to engine families
    # Old step types (without prefix) are assumed to be QE
    step_type_to_family: Dict[str, str] = {}

    # QE step types (prefixed and legacy)
    qe_types = {"scf", "nscf", "relax", ...}
    for step_type in qe_types:
        step_type_to_family[step_type] = "qe"
        step_type_to_family[f"qe_{step_type}"] = "qe"
        ...

    # Wannier90 step types
    w90_types = {"w90_preproc", "w90_run"}
    for step_type in w90_types:
        step_type_to_family[step_type] = "qe"  # ← REMOVE

    # PySCF step types
    pyscf_types = {"pyscf_scf"}
    for step_type in pyscf_types:
        step_type_to_family[step_type] = "pyscf"

    # Collect families from all steps
    families = set()
    for step in steps:
        step_type = step.step_type
        if step_type:
            family = step_type_to_family.get(step_type)
            if family:
                families.add(family)
            elif not step_type.startswith(("qe_", "w90_", "pyscf_")):
                # Legacy step type without prefix - assume QE
                families.add("qe")  # ← CRITICAL: REMOVE THIS
    ...
```

### Fixed Code

```python
def _infer_engine_family_from_steps(steps: List["CalculationStepEntry"]) -> Optional[str]:
    """
    Infer engine_family from step types using DriverRegistry.

    Uses DriverRegistry to look up engine for each step type.
    Returns a single family if all steps belong to one engine, None if mixed/unknown.

    Args:
        steps: List of CalculationStepEntry objects

    Returns:
        Engine family identifier if all steps belong to one family, None otherwise
    """
    if not steps:
        return None

    # Ensure drivers are loaded
    import quantumvitas.drivers
    from quantumvitas.core.driver_registry import DriverRegistry

    families = set()
    for step in steps:
        step_type = step.type  # Use .type which stores public_type
        if step_type and DriverRegistry.is_step_type_registered(step_type):
            engine = DriverRegistry.get_engine_for_step_type(step_type)
            families.add(engine)
        # Unknown step types are ignored - will fail at handler dispatch

    # Return single family if all steps belong to one family
    if len(families) == 1:
        return families.pop()

    # Mixed engines or no recognized step types
    return None
```

### Verification

```bash
# After fix, this test should pass:
pytest tests/gates/test_no_fallbacks.py::TestNoSilentQEFallback -v
```

---

## Fix 2: Remove QE Fallback in `handlers.py` [CRITICAL]

**File**: `src/quantumvitas/execution/handlers.py`
**Function**: `create_handler_map()`
**Lines**: 208-231

### Current Code (BROKEN)

```python
def create_handler_map(...) -> Dict[str, Callable[[Job, "Calculation"], JobResult]]:
    # Ensure drivers are loaded
    import quantumvitas.drivers

    def make_handler(base_handler: HandlerFunc):
        ...

    # Build handler map from registry
    handler_map = {}

    # Try to get handlers from registry for registered engines
    for engine in DriverRegistry.get_all_engines():
        try:
            driver = DriverRegistry.get_driver(engine)
            base_handler = driver.get_handler()
            handler_map[engine] = make_handler(base_handler)
        except Exception as e:
            logger.warning(f"Could not register handler for {engine}: {e}")
            # Fallback to legacy handlers for engines not yet migrated
            if engine == "qe":                                    # ← REMOVE
                handler_map["qe"] = make_handler(qe_step_handler) # ← REMOVE
            # VASP is now migrated - no fallback needed
            # LAMMPS is now migrated - no fallback needed
            ...

    # Legacy fallback: ensure QE is always available (until QE is fully migrated)
    if "qe" not in handler_map:                                   # ← REMOVE
        handler_map["qe"] = make_handler(qe_step_handler)         # ← REMOVE

    return handler_map
```

### Fixed Code

```python
def create_handler_map(
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> Dict[str, Callable[[Job, "Calculation"], JobResult]]:
    """
    Create a handler map for JobExecutor.

    Returns handlers that capture engine_registry and context via closure.
    This delegates to DriverRegistry for all registered drivers.

    Args:
        engine_registry: Engine registry
        context: Execution context (run_id, run_mode, etc.)

    Returns:
        Dict mapping engine name to handler function

    Raises:
        RuntimeError: If a registered driver fails to provide a handler
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    def make_handler(base_handler: HandlerFunc):
        """Create a closure that captures engine_registry and context."""
        def handler(job: Job, calculation: "Calculation") -> JobResult:
            return base_handler(job, calculation, engine_registry, context)
        return handler

    # Build handler map from registry
    handler_map = {}

    # Get handlers from registry for all registered engines
    for engine in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine)
        base_handler = driver.get_handler()
        handler_map[engine] = make_handler(base_handler)

    return handler_map
```

### Verification

```bash
# After fix, this test should pass:
pytest tests/gates/test_registry_routing.py::TestKernelIntegration -v
```

---

## Fix 3: Remove startswith() Patterns in `generalized_steps.py` [HIGH]

**File**: `src/quantumvitas/workflow/generalized_steps.py`
**Function**: `get_generalized_step_from_engine_specific()`
**Lines**: 365-420

### Current Code (BROKEN)

```python
def get_generalized_step_from_engine_specific(engine_specific_step: str) -> Optional[Tuple[str, str]]:
    """..."""
    # Build reverse mapping from MATERIALIZATION_MAP
    for (family, gen_step), specific_step in MATERIALIZATION_MAP.items():
        if specific_step == engine_specific_step:
            return (family, gen_step)

    # Try to infer from prefix
    if engine_specific_step.startswith("qe_"):           # ← REMOVE
        engine_family = "qe"
        step_name = engine_specific_step[3:]
        step_to_generalized = {...}
        gen_step = step_to_generalized.get(step_name)
        if gen_step:
            return (engine_family, gen_step)
    elif engine_specific_step.startswith("w90_"):        # ← REMOVE
        engine_family = "qe"  # w90 is part of qe family
        ...
    elif engine_specific_step.startswith("pyscf_"):      # ← REMOVE
        ...
    elif engine_specific_step.startswith("orca_"):       # ← REMOVE
        ...

    return None
```

### Fixed Code

```python
def get_generalized_step_from_engine_specific(engine_specific_step: str) -> Optional[Tuple[str, str]]:
    """
    Reverse lookup: engine-specific step -> (engine_family, generalized_step).

    Uses MATERIALIZATION_MAP for known mappings and DriverRegistry for step type lookup.

    Args:
        engine_specific_step: Engine-specific step identifier (e.g., "qe_scf", "vasp_relax")

    Returns:
        Tuple of (engine_family, generalized_step) if found, None otherwise
    """
    # Build reverse mapping from MATERIALIZATION_MAP
    for (family, gen_step), specific_step in MATERIALIZATION_MAP.items():
        if specific_step == engine_specific_step:
            return (family, gen_step)

    # Use registry to get engine family for this step type
    from quantumvitas.core.driver_registry import DriverRegistry
    import quantumvitas.drivers  # Ensure loaded

    if DriverRegistry.is_step_type_registered(engine_specific_step):
        engine = DriverRegistry.get_engine_for_step_type(engine_specific_step)
        # Check all materialization maps to find the generalized step
        driver = DriverRegistry.get_driver(engine)
        mat_map = driver.get_materialization_map()
        # Reverse lookup in this engine's materialization map
        for gen_type, spec_type in mat_map.items():
            if spec_type == engine_specific_step:
                return (engine, gen_type)

    return None
```

---

## Fix 4: Remove W90-QE Coupling in `generalized_steps.py` [HIGH]

**File**: `src/quantumvitas/workflow/generalized_steps.py`
**Lines**: 280-296

### Current Code (BROKEN)

```python
def materialize_step_for_engine(public_step_key: str, engine_family: str, registry=None) -> Optional[str]:
    """..."""
    ...
    # Check if the spec's engine matches the requested engine_family
    # For w90 steps, they're part of qe family toolchain
    spec_engine_family = spec.engine
    if spec_engine_family == engine_family:
        return spec.machine_type
    # Special case: w90 steps are part of qe family
    if spec_engine_family == "qe" and engine_family == "qe" and spec.machine_type.startswith("w90_"):  # ← REMOVE
        return spec.machine_type                                                                        # ← REMOVE
    ...
```

### Fixed Code

```python
def materialize_step_for_engine(public_step_key: str, engine_family: str, registry=None) -> Optional[str]:
    """..."""
    ...
    # Check if the spec's engine matches the requested engine_family
    spec_engine_family = spec.engine
    if spec_engine_family == engine_family:
        return spec.machine_type

    # No special cases - each driver is responsible for its own step types
    # W90 is a separate driver; its step types are registered with engine="w90"
    ...
```

---

## Fix 5: Use Dynamic Engine List in `calculation.py` [MEDIUM]

**File**: `src/quantumvitas/calculation/calculation.py`
**Lines**: 396, 555 (two identical occurrences)

### Current Code (SUBOPTIMAL)

```python
# Lines 396, 555 (identical pattern in two places)
for engine_family in ["qe", "vasp", "orca", "pyscf", "cp2k", "lammps", "w90"]:
    try:
        materialized = DriverRegistry.materialize_step_type(
            engine_family,
            f"GEN_{step_type.upper()}" if not step_type.upper().startswith("GEN_") else step_type.upper()
        )
        if materialized:
            engine_name = engine_family
            break
    except Exception:
        continue
```

### Fixed Code

```python
# Lines 396, 555 (apply to both)
for engine_family in DriverRegistry.get_all_engines():
    try:
        gen_type = f"GEN_{step_type.upper()}" if not step_type.upper().startswith("GEN_") else step_type.upper()
        materialized = DriverRegistry.materialize_step_type(engine_family, gen_type)
        if materialized:
            engine_name = engine_family
            break
    except Exception:
        continue
```

---

## Execution Order

Apply fixes in this order to minimize test failures during the process:

1. **Fix 2** (handlers.py) - Remove runtime fallback first
2. **Fix 1** (models.py) - Remove inference fallback
3. **Fix 3** (generalized_steps.py) - Remove startswith patterns
4. **Fix 4** (generalized_steps.py) - Remove W90-QE coupling
5. **Fix 5** (calculation.py) - Use dynamic engine list

---

## Verification Commands

After all fixes are applied:

```bash
# Run all gate tests
pytest tests/gates/ -v

# Run full test suite
pytest tests/ -v

# Static verification
grep -rn 'families.add("qe")' src/quantumvitas/core/
# Expected: Empty (no matches)

grep -rn 'if "qe" not in handler_map' src/quantumvitas/execution/
# Expected: Empty (no matches)

grep -rn 'startswith("qe_' src/quantumvitas/workflow/generalized_steps.py
# Expected: Empty (no matches)
```

---

## Risk Assessment

| Fix | Risk Level | Rollback Strategy |
|-----|------------|-------------------|
| Fix 1 | Medium | Revert function to original |
| Fix 2 | Low | Add fallback back |
| Fix 3 | Medium | Restore prefix detection |
| Fix 4 | Low | Add special case back |
| Fix 5 | Low | Hardcode list again |

---

## Post-Fix Validation Checklist

- [ ] All `pytest tests/gates/` tests pass
- [ ] All `pytest tests/` tests pass
- [ ] `grep -rn 'families.add("qe")' src/quantumvitas/core/` returns empty
- [ ] `grep -rn 'qe.*fallback' src/quantumvitas/execution/handlers.py` returns empty
- [ ] Manual test: Create step with unknown type → Verify UnknownStepTypeError raised
- [ ] Manual test: Create step with typo (e.g., "qe_scff") → Verify helpful error with suggestion

---

## Summary

| Status | Description |
|--------|-------------|
| **Code Changes Required** | YES |
| **Number of Fixes** | 5 |
| **Files Modified** | 3 |
| **Estimated LOC Changed** | ~80 |
| **Breaking Changes** | None (removing fallbacks exposes bugs that were previously silent) |
