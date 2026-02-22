# Engine Registry and Dispatch

**Version**: 1.0
**Status**: SPECIFICATION

---

## 1. Overview

This document specifies how engine drivers are discovered, registered, and how dispatch works from step type to execution. All routing is explicit with no prefix matching or fallbacks.

---

## 2. Registry Architecture

### 2.1 Three Registries

| Registry | Key | Value | Purpose |
|----------|-----|-------|---------|
| `DRIVER_REGISTRY` | `engine_family` | `EngineDriver` | Engine → Driver |
| `STEP_TYPE_REGISTRY` | `step_type_id` | `StepTypeSpec` | Step type → Spec |
| `MATERIALIZATION_REGISTRY` | `(engine, gen_type)` | `machine_type` | GEN → SPEC |

### 2.2 Registry Structure

```python
# Conceptual structure (actual implementation may differ)

DRIVER_REGISTRY: dict[str, EngineDriver] = {
    "vasp": VASPDriver(),
    "qe": QEDriver(),
    "orca": ORCADriver(),
    # ...
}

STEP_TYPE_REGISTRY: dict[str, StepTypeSpec] = {
    "vasp_scf": StepTypeSpec(id="vasp_scf", engine="vasp", ...),
    "vasp_relax": StepTypeSpec(id="vasp_relax", engine="vasp", ...),
    "pw_scf": StepTypeSpec(id="pw_scf", engine="qe", ...),
    # ...
}

MATERIALIZATION_REGISTRY: dict[tuple[str, str], str] = {
    ("vasp", "GEN_SCF"): "vasp_scf",
    ("vasp", "GEN_RELAX"): "vasp_relax",
    ("qe", "GEN_SCF"): "pw_scf",
    # ...
}
```

---

## 3. Driver Discovery

### 3.1 Discovery Mechanism

Drivers are discovered via **package auto-import**:

```
src/qmatsuite/drivers/
├── __init__.py          # Discovery entry point
├── vasp/
│   └── __init__.py      # Calls DriverRegistry.register()
├── qe/
│   └── __init__.py
├── orca/
│   └── __init__.py
└── ...
```

### 3.2 Discovery Algorithm

```python
# drivers/__init__.py

import importlib
import pkgutil
from pathlib import Path

def discover_drivers():
    """
    Import all driver packages to trigger registration.

    Each driver's __init__.py MUST call DriverRegistry.register().
    """
    drivers_dir = Path(__file__).parent

    for finder, name, is_pkg in pkgutil.iter_modules([str(drivers_dir)]):
        if is_pkg:
            try:
                importlib.import_module(f".{name}", package=__name__)
            except ImportError as e:
                # Log warning but don't fail
                # Driver may have optional dependencies
                logger.warning(f"Failed to load driver '{name}': {e}")

# Trigger discovery on import
discover_drivers()
```

### 3.3 Driver Registration

Each driver package registers itself:

```python
# drivers/vasp/__init__.py

from .driver import VASPDriver
from qmatsuite.core.driver_registry import DriverRegistry

# Register at import time
DriverRegistry.register(VASPDriver())
```

### 3.4 Registration Validation

```python
class DriverRegistry:
    _drivers: dict[str, EngineDriver] = {}
    _step_types: dict[str, StepTypeSpec] = {}
    _materializations: dict[tuple[str, str], str] = {}

    @classmethod
    def register(cls, driver: EngineDriver) -> None:
        family = driver.engine_family

        # ── Validate uniqueness ──
        if family in cls._drivers:
            raise DuplicateEngineError(
                f"Engine '{family}' already registered"
            )

        # ── Validate API version ──
        cls._validate_api_version(driver)

        # ── Register driver ──
        cls._drivers[family] = driver

        # ── Register step types ──
        for spec in driver.get_step_type_specs():
            if spec.id in cls._step_types:
                raise DuplicateStepTypeError(
                    f"Step type '{spec.id}' already registered by "
                    f"'{cls._step_types[spec.id].engine}'"
                )
            if spec.engine != family:
                raise EngineMismatchError(
                    f"Step type '{spec.id}' declares engine '{spec.engine}' "
                    f"but driver is '{family}'"
                )
            cls._step_types[spec.id] = spec

        # ── Register materializations ──
        for gen_type, machine_type in driver.get_materialization_map().items():
            key = (family, gen_type)
            if key in cls._materializations:
                raise DuplicateMaterializationError(
                    f"Materialization ({family}, {gen_type}) already registered"
                )
            # Validate machine_type is known
            if machine_type not in cls._step_types:
                raise UnknownMachineTypeError(
                    f"Materialization target '{machine_type}' not in step types"
                )
            cls._materializations[key] = machine_type
```

---

## 4. Dispatch: Step Type to Execution

### 4.1 Dispatch Flow

```
User Request
    │
    ├─► Generalized step type?
    │       │
    │       ▼ [L1: Materialize]
    │   machine_type = MATERIALIZATION_REGISTRY[(engine, gen_type)]
    │       │
    │       ▼
    │   ┌────────────────────┐
    │   │ machine_type known │
    │   └────────────────────┘
    │
    ▼ [L2: Step Type Lookup]
spec = STEP_TYPE_REGISTRY[machine_type]
    │
    ▼ [L3: Driver Lookup]
driver = DRIVER_REGISTRY[spec.engine]
    │
    ├─► handler = driver.get_handler()
    └─► recipe_class = driver.get_recipe_class()
```

### 4.2 L1: Materialization (GEN → SPEC)

```python
def materialize_step_type(
    engine_family: str,
    generalized_type: str,
) -> str:
    """
    Convert generalized step type to machine step type.

    Args:
        engine_family: Target engine (e.g., "vasp")
        generalized_type: Generalized type (e.g., "GEN_SCF")

    Returns:
        Machine step type (e.g., "vasp_scf")

    Raises:
        UnknownMaterializationError: If (engine, gen_type) not registered
    """
    key = (engine_family, generalized_type)

    if key not in MATERIALIZATION_REGISTRY:
        known = [k for k in MATERIALIZATION_REGISTRY if k[0] == engine_family]
        raise UnknownMaterializationError(
            f"No materialization for ({engine_family}, {generalized_type}).\n"
            f"Known for {engine_family}: {[k[1] for k in known]}"
        )

    return MATERIALIZATION_REGISTRY[key]
```

### 4.3 L2: Step Type Lookup (SPEC → Engine)

```python
def get_step_type_spec(step_type: str) -> StepTypeSpec:
    """
    Look up step type specification.

    Args:
        step_type: Machine step type (e.g., "vasp_scf")

    Returns:
        StepTypeSpec with engine, executable, etc.

    Raises:
        UnknownStepTypeError: If step type not registered
    """
    if step_type not in STEP_TYPE_REGISTRY:
        # Find similar types for helpful error
        similar = _find_similar(step_type, STEP_TYPE_REGISTRY.keys())
        raise UnknownStepTypeError(
            f"Step type '{step_type}' is not registered.\n"
            f"Did you mean: {', '.join(similar[:3])}?\n"
            f"Known types: {', '.join(sorted(STEP_TYPE_REGISTRY.keys()))}"
        )

    return STEP_TYPE_REGISTRY[step_type]
```

### 4.4 L3: Driver Lookup (Engine → Driver)

```python
def get_driver(engine_family: str) -> EngineDriver:
    """
    Get driver for engine family.

    Args:
        engine_family: Engine identifier (e.g., "vasp")

    Returns:
        EngineDriver instance

    Raises:
        UnknownEngineError: If engine not registered
    """
    if engine_family not in DRIVER_REGISTRY:
        raise UnknownEngineError(
            f"No driver registered for engine '{engine_family}'.\n"
            f"Available engines: {', '.join(sorted(DRIVER_REGISTRY.keys()))}"
        )

    return DRIVER_REGISTRY[engine_family]


def get_driver_for_step_type(step_type: str) -> EngineDriver:
    """
    Get driver for a step type (convenience combining L2 + L3).

    Args:
        step_type: Machine step type

    Returns:
        EngineDriver that handles this step type

    Raises:
        UnknownStepTypeError: If step type not registered
    """
    spec = get_step_type_spec(step_type)
    return get_driver(spec.engine)
```

---

## 5. Explicit Routing Rules

### 5.1 PROHIBITED Patterns

```python
# ❌ PROHIBITED: Prefix-based inference
if step_type.startswith("vasp_"):
    engine = "vasp"

# ❌ PROHIBITED: Silent fallback
engine = mapping.get(step_type, "qe")

# ❌ PROHIBITED: Pattern matching
if "scf" in step_type:
    handler = scf_handler

# ❌ PROHIBITED: Default returns
def get_engine(step_type):
    return engines.get(step_type)  # Returns None for unknown
```

### 5.2 REQUIRED Patterns

```python
# ✅ REQUIRED: Explicit lookup with hard error
spec = STEP_TYPE_REGISTRY[step_type]  # KeyError if unknown

# ✅ REQUIRED: Explicit lookup with helpful error
spec = get_step_type_spec(step_type)  # UnknownStepTypeError with hints

# ✅ REQUIRED: Full dispatch chain
driver = get_driver_for_step_type(step_type)
handler = driver.get_handler()
```

---

## 6. Handler and Recipe Dispatch

### 6.1 Handler Dispatch

```python
# execution/dispatch.py

def get_handler_for_step(step: Step) -> Callable:
    """
    Get handler function for a step.

    NO FALLBACKS. Unknown step types raise UnknownStepTypeError.
    """
    driver = get_driver_for_step_type(step.step_type)
    return driver.get_handler()


def execute_step(step: Step, job: Job, ctx: Context) -> JobResult:
    """Execute a step using its driver's handler."""
    handler = get_handler_for_step(step)
    return handler(job, ctx)
```

### 6.2 Recipe Dispatch

```python
def get_recipe_for_step(step: Step) -> BaseRecipe:
    """
    Get recipe instance for a step.

    NO FALLBACKS. Unknown step types raise UnknownStepTypeError.
    """
    driver = get_driver_for_step_type(step.step_type)
    recipe_class = driver.get_recipe_class()
    return recipe_class(step)
```

---

## 7. Engine Family Determination

### 7.1 From Step Type

```python
def determine_engine_family(step_type: str) -> str:
    """
    Determine engine family for a step type.

    This is the ONLY allowed way to determine engine from step type.
    NO PREFIX MATCHING. NO FALLBACKS.

    Raises:
        UnknownStepTypeError: If step type not registered
    """
    spec = get_step_type_spec(step_type)
    return spec.engine
```

### 7.2 From Calculation

```python
def determine_calculation_engine(calculation: Calculation) -> str:
    """
    Determine primary engine family for a calculation.

    Based on first step's engine. Multi-engine calculations
    may have multiple families.
    """
    if not calculation.steps:
        raise EmptyCalculationError("Calculation has no steps")

    first_step = calculation.steps[0]
    return determine_engine_family(first_step.step_type)
```

---

## 8. Error Messages

### 8.1 Error Format

All routing errors MUST include:
1. What was requested
2. Why it failed
3. What alternatives exist

```python
class UnknownStepTypeError(Exception):
    def __init__(self, step_type: str, known_types: list[str]):
        similar = find_similar(step_type, known_types, limit=3)

        message = f"Step type '{step_type}' is not registered.\n"
        if similar:
            message += f"Did you mean: {', '.join(similar)}?\n"
        message += f"Known step types: {', '.join(sorted(known_types)[:20])}"
        if len(known_types) > 20:
            message += f"... ({len(known_types) - 20} more)"

        super().__init__(message)
        self.step_type = step_type
        self.known_types = known_types
```

### 8.2 Example Error Output

```
UnknownStepTypeError: Step type 'vaps_scf' is not registered.
Did you mean: vasp_scf, vasp_relax, vasp_md?
Known step types: cp2k_md, cp2k_relax, cp2k_scf, lammps_md, lammps_relax,
orca_freq, orca_opt, orca_scf, pw_bands, pw_dos, pw_md, pw_nscf, pw_relax,
pw_scf, pyscf_analysis, pyscf_freq, pyscf_mp2, pyscf_scf, pyscf_td,
vasp_bands... (15 more)
```

---

## 9. Logging and Auditability

### 9.1 Debug Logging

```python
def get_driver_for_step_type(step_type: str) -> EngineDriver:
    logger.debug(f"L2: Looking up step type '{step_type}'")
    spec = get_step_type_spec(step_type)
    logger.debug(f"L2: Found spec: engine={spec.engine}, exe={spec.executable}")

    logger.debug(f"L3: Looking up driver for engine '{spec.engine}'")
    driver = get_driver(spec.engine)
    logger.debug(f"L3: Found driver: {driver.display_name}")

    return driver
```

### 9.2 Audit Trail

Each step execution logs the full routing chain:

```
INFO: Executing step step_001 (vasp_scf)
DEBUG: L2: step type lookup: vasp_scf → engine=vasp
DEBUG: L3: driver lookup: vasp → VASPDriver
DEBUG: Handler: VASPDriver.get_handler()
DEBUG: Recipe: VASPRecipe
INFO: Step step_001 completed in 45.2s
```

---

## 10. Registry Queries

### 10.1 Introspection API

```python
class DriverRegistry:
    @classmethod
    def list_engines(cls) -> list[str]:
        """List all registered engine families."""
        return sorted(cls._drivers.keys())

    @classmethod
    def list_step_types(cls, engine: str | None = None) -> list[str]:
        """List step types, optionally filtered by engine."""
        if engine is None:
            return sorted(cls._step_types.keys())
        return sorted(
            k for k, v in cls._step_types.items()
            if v.engine == engine
        )

    @classmethod
    def list_materializations(cls, engine: str | None = None) -> list[tuple[str, str, str]]:
        """List (engine, gen_type, machine_type) tuples."""
        result = []
        for (eng, gen), machine in cls._materializations.items():
            if engine is None or eng == engine:
                result.append((eng, gen, machine))
        return sorted(result)
```

### 10.2 Validation Queries

```python
    @classmethod
    def is_valid_step_type(cls, step_type: str) -> bool:
        """Check if step type is registered (no exception)."""
        return step_type in cls._step_types

    @classmethod
    def is_valid_engine(cls, engine: str) -> bool:
        """Check if engine is registered (no exception)."""
        return engine in cls._drivers
```

---

## 11. Kernel Aggregator Files

### 11.1 After Migration

After driver migration, kernel aggregator files become thin dispatchers:

```python
# execution/handlers.py (after migration)

from qmatsuite.core.driver_registry import get_driver_for_step_type

def get_handler_for_step(step: Step) -> Callable:
    """Dispatch to driver's handler. NO ENGINE-SPECIFIC CODE HERE."""
    return get_driver_for_step_type(step.step_type).get_handler()
```

```python
# execution/recipes.py (after migration)

from qmatsuite.core.driver_registry import get_driver

def get_recipe_class(engine_family: str) -> type[BaseRecipe]:
    """Dispatch to driver's recipe. NO ENGINE-SPECIFIC CODE HERE."""
    return get_driver(engine_family).get_recipe_class()
```

### 11.2 Prohibited Content

These files MUST NOT contain:
- Engine-specific handler functions
- Engine-specific recipe classes
- Engine name conditionals
- Hardcoded step type sets
- Prefix-based routing

---

## 12. Testing Requirements

### 12.1 Registry Tests

```python
def test_unknown_step_type_raises():
    with pytest.raises(UnknownStepTypeError) as exc:
        get_step_type_spec("nonexistent_step")
    assert "nonexistent_step" in str(exc.value)
    assert "Did you mean" in str(exc.value)

def test_unknown_engine_raises():
    with pytest.raises(UnknownEngineError) as exc:
        get_driver("nonexistent_engine")
    assert "Available engines" in str(exc.value)

def test_no_prefix_matching():
    # Even if vasp_* exists, vasp_unknown should fail
    with pytest.raises(UnknownStepTypeError):
        get_step_type_spec("vasp_unknown_type")
```

### 12.2 Dispatch Tests

```python
def test_dispatch_chain_logged(caplog):
    with caplog.at_level(logging.DEBUG):
        driver = get_driver_for_step_type("vasp_scf")
    assert "L2" in caplog.text
    assert "L3" in caplog.text

def test_handler_dispatch_no_fallback():
    # Verify dispatch uses registry, not hardcoded logic
    driver = get_driver_for_step_type("vasp_scf")
    handler = driver.get_handler()
    assert callable(handler)
```
