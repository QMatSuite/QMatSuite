# Registry and Dispatch Contract

**Version**: 1.0
**Date**: 2026-01-20
**Status**: IMPLEMENTATION CONTRACT

This document defines the **exact contract** for routing step types to drivers. It explicitly addresses and closes the CRITICAL vulnerability (prefix-based detection + QE fallback).

---

## 1. The CRITICAL Vulnerability (MUST FIX FIRST)

### 1.1 Current Dangerous Code

**File**: `src/quantumvitas/core/calc_identity.py`
**Function**: `_infer_engine_family_from_machine_types()`
**Lines**: 96-108

```python
def _infer_engine_family_from_machine_types(machine_types: List[str]) -> Optional[str]:
    # ...
    for machine_type in machine_types:
        if machine_type.startswith("qe_") or machine_type in ("w90_preproc", "w90_run"):
            families.add("qe")
        elif machine_type.startswith("pyscf_"):
            families.add("pyscf")
        elif machine_type.startswith("w90_"):
            families.add("w90")
        else:
            # Unknown prefix - could be legacy step type
            # Assume QE for backward compatibility   <-- CRITICAL VULNERABILITY
            families.add("qe")
```

### 1.2 Additional Dangerous Locations

| File | Line | Pattern | Danger |
|------|------|---------|--------|
| `calculation/calculation.py` | 339 | `.get("engine", "qe")` | Silent QE default |
| `calculation/calculation.py` | 455 | `.get("engine", "qe")` | Silent QE default |
| `workflow/generalized_steps.py` | 368 | `startswith("pyscf_")` | Prefix inference |
| `workflow/generalized_steps.py` | 379 | `startswith("orca_")` | Prefix inference |

### 1.3 Required Fix (Contract)

**All routing MUST use explicit registry lookup. No exceptions.**

```python
# PROHIBITED (any of these patterns)
if step_type.startswith("vasp_"): ...
engine = data.get("engine", "qe")
families.add("qe")  # as fallback

# REQUIRED
spec = STEP_TYPE_REGISTRY.get(step_type)
if spec is None:
    raise UnknownStepTypeError(step_type)
engine = spec.engine
```

---

## 2. Three-Level Mapping Contract

### 2.1 Level 1: GEN → SPEC (Materialization)

**Purpose**: Convert generalized step type to machine step type

**Input**: `(engine_family: str, generalized_type: str)`
**Output**: `machine_step_type: str`

**Contract**:
```python
def materialize(engine_family: str, gen_type: str) -> str:
    """
    Convert (engine, GEN_*) to machine step type.

    MUST raise UnknownMaterializationError if not found.
    MUST NOT infer from prefixes.
    MUST NOT return default value.
    """
    key = (engine_family, gen_type)
    result = MATERIALIZATION_REGISTRY.get(key)
    if result is None:
        raise UnknownMaterializationError(
            f"No materialization for ({engine_family}, {gen_type}). "
            f"Known for {engine_family}: {_list_gen_types_for_engine(engine_family)}"
        )
    return result
```

**Registry Source**: Aggregated from `driver.get_materialization_map()` for each registered driver.

**Example Entries**:
```python
MATERIALIZATION_REGISTRY = {
    ("vasp", "GEN_SCF"): "vasp_scf",
    ("vasp", "GEN_RELAX"): "vasp_relax",
    ("vasp", "GEN_MD"): "vasp_md",
    ("orca", "GEN_SCF"): "orca_scf",
    ("orca", "GEN_RELAX"): "orca_opt",
    ("pyscf", "GEN_SCF"): "pyscf_scf",
    ("lammps", "GEN_RELAX"): "lammps_relax",
    ("lammps", "GEN_MD"): "lammps_md",
    ("cp2k", "GEN_SCF"): "cp2k_scf",
    ("cp2k", "GEN_RELAX"): "cp2k_relax",
    ("cp2k", "GEN_MD"): "cp2k_md",
    # QE entries remain in kernel until QE migration
    ("qe", "GEN_SCF"): "qe_scf",
    ("qe", "GEN_RELAX"): "qe_relax",
    # ...
}
```

### 2.2 Level 2: SPEC → Engine (Step Type Lookup)

**Purpose**: Get engine family from machine step type

**Input**: `step_type: str`
**Output**: `StepTypeSpec` (contains `.engine`)

**Contract**:
```python
def get_step_type_spec(step_type: str) -> StepTypeSpec:
    """
    Look up step type specification.

    MUST raise UnknownStepTypeError if not found.
    MUST NOT infer from prefix.
    MUST NOT return default.
    """
    spec = STEP_TYPE_REGISTRY.get(step_type)
    if spec is None:
        similar = _find_similar_types(step_type)
        raise UnknownStepTypeError(
            f"Step type '{step_type}' is not registered.\n"
            f"Did you mean: {', '.join(similar[:3])}?\n"
            f"Known types: {', '.join(sorted(STEP_TYPE_REGISTRY.keys())[:20])}..."
        )
    return spec
```

**Registry Source**: Aggregated from `driver.get_step_type_specs()` for each registered driver.

### 2.3 Level 3: Engine → Driver (Driver Lookup)

**Purpose**: Get driver instance for engine family

**Input**: `engine_family: str`
**Output**: `EngineDriver`

**Contract**:
```python
def get_driver(engine_family: str) -> EngineDriver:
    """
    Get driver for engine family.

    MUST raise UnknownEngineError if not found.
    MUST NOT return default driver.
    """
    driver = DRIVER_REGISTRY.get(engine_family)
    if driver is None:
        raise UnknownEngineError(
            f"No driver for engine '{engine_family}'.\n"
            f"Available: {', '.join(sorted(DRIVER_REGISTRY.keys()))}"
        )
    return driver
```

---

## 3. Error Classes and Messages

### 3.1 Exception Hierarchy

```python
# src/quantumvitas/core/driver_exceptions.py

class DriverError(Exception):
    """Base class for driver-related errors."""
    pass

class UnknownStepTypeError(DriverError):
    """Raised when step type is not registered."""
    def __init__(self, step_type: str, known_types: list[str] | None = None):
        self.step_type = step_type
        self.known_types = known_types or []
        similar = self._find_similar()
        msg = f"Step type '{step_type}' is not registered."
        if similar:
            msg += f"\nDid you mean: {', '.join(similar[:3])}?"
        if self.known_types:
            msg += f"\nKnown types: {', '.join(sorted(self.known_types)[:20])}"
        super().__init__(msg)

class UnknownEngineError(DriverError):
    """Raised when engine family is not registered."""
    def __init__(self, engine: str, available: list[str] | None = None):
        self.engine = engine
        self.available = available or []
        msg = f"No driver registered for engine '{engine}'."
        if self.available:
            msg += f"\nAvailable engines: {', '.join(sorted(self.available))}"
        super().__init__(msg)

class UnknownMaterializationError(DriverError):
    """Raised when GEN→SPEC mapping not found."""
    def __init__(self, engine: str, gen_type: str, known_gen_types: list[str] | None = None):
        self.engine = engine
        self.gen_type = gen_type
        msg = f"No materialization for ({engine}, {gen_type})."
        if known_gen_types:
            msg += f"\nKnown generalized types for {engine}: {', '.join(known_gen_types)}"
        super().__init__(msg)

class DuplicateStepTypeError(DriverError):
    """Raised when step type already registered."""
    pass

class DuplicateEngineError(DriverError):
    """Raised when engine already registered."""
    pass
```

### 3.2 Error Message Guidelines

All error messages MUST include:
1. **What failed**: The specific value that wasn't found
2. **Suggestions**: Similar known values (using Levenshtein distance)
3. **Available options**: List of valid alternatives

---

## 4. Registry Implementation Contract

### 4.1 DriverRegistry Class

```python
# src/quantumvitas/core/driver_registry.py

class DriverRegistry:
    """
    Singleton registry for engine drivers.

    Drivers register at import time via DriverRegistry.register().
    Kernel queries this registry for all routing decisions.
    """

    _instance: ClassVar[Optional["DriverRegistry"]] = None
    _drivers: Dict[str, EngineDriver]
    _step_types: Dict[str, StepTypeSpec]
    _materializations: Dict[Tuple[str, str], str]
    _initialized: bool

    def __new__(cls) -> "DriverRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._drivers = {}
            cls._instance._step_types = {}
            cls._instance._materializations = {}
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def register(cls, driver: EngineDriver) -> None:
        """Register a driver. Called by driver packages at import."""
        instance = cls()
        family = driver.engine_family

        # Validate not duplicate
        if family in instance._drivers:
            raise DuplicateEngineError(f"Engine '{family}' already registered")

        # Register driver
        instance._drivers[family] = driver

        # Register step types
        for spec in driver.get_step_type_specs():
            if spec.id in instance._step_types:
                raise DuplicateStepTypeError(
                    f"Step type '{spec.id}' already registered"
                )
            instance._step_types[spec.id] = spec

        # Register materializations
        for gen_type, machine_type in driver.get_materialization_map().items():
            key = (family, gen_type)
            instance._materializations[key] = machine_type

    @classmethod
    def get_driver(cls, engine_family: str) -> EngineDriver:
        """Get driver by family. Raises UnknownEngineError if not found."""
        instance = cls()
        if engine_family not in instance._drivers:
            raise UnknownEngineError(engine_family, list(instance._drivers.keys()))
        return instance._drivers[engine_family]

    @classmethod
    def get_step_type_spec(cls, step_type: str) -> StepTypeSpec:
        """Get spec by step type. Raises UnknownStepTypeError if not found."""
        instance = cls()
        if step_type not in instance._step_types:
            raise UnknownStepTypeError(step_type, list(instance._step_types.keys()))
        return instance._step_types[step_type]

    @classmethod
    def get_driver_for_step_type(cls, step_type: str) -> EngineDriver:
        """Get driver that handles step type. Raises on unknown."""
        spec = cls.get_step_type_spec(step_type)
        return cls.get_driver(spec.engine)

    @classmethod
    def materialize(cls, engine_family: str, gen_type: str) -> str:
        """Get machine type for (engine, gen_type). Raises on unknown."""
        instance = cls()
        key = (engine_family, gen_type)
        if key not in instance._materializations:
            known = [g for (e, g) in instance._materializations if e == engine_family]
            raise UnknownMaterializationError(engine_family, gen_type, known)
        return instance._materializations[key]

    @classmethod
    def is_known_step_type(cls, step_type: str) -> bool:
        """Check if step type is registered (no exception)."""
        return step_type in cls()._step_types

    @classmethod
    def is_known_engine(cls, engine_family: str) -> bool:
        """Check if engine is registered (no exception)."""
        return engine_family in cls()._drivers

    @classmethod
    def list_engines(cls) -> List[str]:
        """List all registered engine families."""
        return sorted(cls()._drivers.keys())

    @classmethod
    def list_step_types(cls, engine: Optional[str] = None) -> List[str]:
        """List step types, optionally filtered by engine."""
        instance = cls()
        if engine is None:
            return sorted(instance._step_types.keys())
        return sorted(k for k, v in instance._step_types.items() if v.engine == engine)
```

### 4.2 Where Logic Lives

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `DriverRegistry` | `core/driver_registry.py` | Storage, lookup, validation |
| `EngineDriver` protocol | `core/driver_protocol.py` | Interface definition |
| Exception classes | `core/driver_exceptions.py` | Error types |
| Driver implementations | `drivers/<engine>/driver.py` | Per-engine logic |
| Step type specs | Returned by driver | Per-engine declaration |
| Materialization map | Returned by driver | Per-engine GEN→SPEC |

---

## 5. Dispatch Flow Contract

### 5.1 Handler Dispatch

**File to modify**: `src/quantumvitas/execution/handlers.py`

**Current** (after migration):
```python
def get_handler_for_engine(engine_family: str) -> HandlerFunc:
    """
    Get handler for engine.

    Uses DriverRegistry for migrated engines.
    Uses legacy map for QE (until QE migration).
    """
    # Try driver registry first
    if DriverRegistry.is_known_engine(engine_family):
        driver = DriverRegistry.get_driver(engine_family)
        return driver.get_handler()

    # Legacy fallback for QE only (explicit, not silent)
    if engine_family == "qe":
        return qe_step_handler

    # No fallback - raise
    raise UnknownEngineError(engine_family)
```

### 5.2 Recipe Dispatch

**File to modify**: `src/quantumvitas/execution/recipes.py`

**Current** (after migration):
```python
def get_recipe_class(engine_family: str) -> Type[BaseRecipe]:
    """
    Get recipe class for engine.

    Uses DriverRegistry for migrated engines.
    Uses legacy class for QE (until QE migration).
    """
    # Try driver registry first
    if DriverRegistry.is_known_engine(engine_family):
        driver = DriverRegistry.get_driver(engine_family)
        return driver.get_recipe_class()

    # Legacy fallback for QE only
    if engine_family == "qe":
        return QERecipe

    # No fallback - raise
    raise UnknownEngineError(engine_family)
```

### 5.3 Materialization Dispatch

**File to modify**: `src/quantumvitas/workflow/generalized_steps.py`

**Current** (after migration):
```python
def materialize_step_type(engine_family: str, gen_type: str) -> str:
    """
    Convert generalized to machine step type.

    Uses DriverRegistry for migrated engines.
    Uses legacy MATERIALIZATION_MAP for QE.
    """
    # Try driver registry first
    try:
        return DriverRegistry.materialize(engine_family, gen_type)
    except UnknownMaterializationError:
        pass

    # Legacy fallback for QE only
    key = (engine_family, gen_type)
    if key in _LEGACY_QE_MATERIALIZATION_MAP:
        return _LEGACY_QE_MATERIALIZATION_MAP[key]

    raise UnknownMaterializationError(engine_family, gen_type)
```

---

## 6. Test Contract for Registry

### 6.1 Must-Pass Tests

```python
# tests/core/test_driver_registry.py

class TestRegistryContract:
    """Tests that enforce the registry contract."""

    def test_unknown_step_type_raises(self):
        """Unknown step type MUST raise UnknownStepTypeError."""
        with pytest.raises(UnknownStepTypeError) as exc:
            DriverRegistry.get_step_type_spec("nonexistent_xyz")
        assert "nonexistent_xyz" in str(exc.value)
        assert "Did you mean" in str(exc.value) or "Known types" in str(exc.value)

    def test_unknown_engine_raises(self):
        """Unknown engine MUST raise UnknownEngineError."""
        with pytest.raises(UnknownEngineError) as exc:
            DriverRegistry.get_driver("nonexistent_engine")
        assert "Available engines" in str(exc.value)

    def test_typo_does_not_route_to_qe(self):
        """Typos MUST NOT silently route to QE."""
        typos = ["vaps_scf", "vasp_scff", "orce_scf", "pyscf_scff"]
        for typo in typos:
            with pytest.raises(UnknownStepTypeError):
                DriverRegistry.get_step_type_spec(typo)

    def test_prefix_match_not_used(self):
        """New prefix MUST NOT infer to existing engine."""
        # Even though vasp_* exists, vasp_newtype should fail
        with pytest.raises(UnknownStepTypeError):
            DriverRegistry.get_step_type_spec("vasp_newtype_xyz")

    def test_no_silent_qe_default(self):
        """No routing path should silently default to QE."""
        # This verifies calc_identity fix
        from quantumvitas.core.calc_identity import _infer_engine_family_from_machine_types
        # Unknown type should return None, not "qe"
        result = _infer_engine_family_from_machine_types(["unknown_xyz"])
        assert result is None or result != "qe"  # Either None or explicit error


class TestMigrationPrereq:
    """Tests that must pass BEFORE any engine migration."""

    def test_no_startswith_in_routing(self):
        """No startswith patterns in calc_identity for routing."""
        import ast
        from pathlib import Path

        source = Path("src/quantumvitas/core/calc_identity.py").read_text()
        tree = ast.parse(source)

        # Check for .startswith() calls on step types
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "startswith":
                        # This is allowed only in specific non-routing contexts
                        # The test should fail if startswith is used for engine detection
                        pass  # Implement detailed check
```

---

## 7. Enforcement Mechanism

### 7.1 CI Gate

```yaml
# .github/workflows/no_fallbacks.yml
- name: Check no QE fallback
  run: |
    # Search for silent QE fallbacks
    if grep -rn 'families.add("qe")' src/quantumvitas/core/calc_identity.py; then
      echo "FAIL: Silent QE fallback still exists"
      exit 1
    fi
    if grep -rn '\.get("engine", "qe")' src/quantumvitas/calculation/; then
      echo "FAIL: Silent engine=qe default found"
      exit 1
    fi
```

### 7.2 Pre-commit Hook (Optional)

```python
# scripts/check_no_fallbacks.py
"""Pre-commit hook to prevent reintroduction of fallbacks."""

import re
import sys
from pathlib import Path

PROHIBITED_PATTERNS = [
    (r'families\.add\("qe"\)', "Silent QE fallback"),
    (r'\.get\("engine",\s*"qe"\)', "Silent engine=qe default"),
    (r'startswith\("vasp_"\)', "Prefix-based VASP detection"),
    (r'startswith\("orca_"\)', "Prefix-based ORCA detection"),
]

def check_file(path: Path) -> list[str]:
    content = path.read_text()
    violations = []
    for pattern, description in PROHIBITED_PATTERNS:
        if re.search(pattern, content):
            violations.append(f"{path}: {description}")
    return violations

# Run on changed files
```
