# Driver Bundle Minimum Surface

**Version**: 1.0
**Date**: 2026-01-20
**Status**: IMPLEMENTATION CONTRACT

This document defines the **minimal required interface** for driver bundles to avoid "fill 30 fields" boilerplate while maintaining useful capabilities.

---

## 1. Design Principles

1. **Minimal MUST**: Only what's needed for routing and execution
2. **Sensible defaults**: Kernel provides defaults for SHOULD/PLUGIN
3. **No over-abstraction**: Keep it simple and practical
4. **Backward compatible**: Existing behavior preserved

---

## 2. MUST Interface (Required, 7 Items)

A driver bundle MUST implement these 7 items. Without them, registration fails.

### 2.1 Three Properties

```python
class MyDriver:
    @property
    def engine_family(self) -> str:
        """Unique engine identifier. E.g., 'vasp', 'orca'"""
        return "myengine"

    @property
    def display_name(self) -> str:
        """Human-readable name for UI/logs."""
        return "My Engine"

    @property
    def driver_api_version(self) -> str:
        """Semver string. Must be '1.x.x' for current kernel."""
        return "1.0.0"
```

### 2.2 Four Methods

```python
    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return step types this driver handles."""
        return [
            StepTypeSpec(id="myengine_scf", engine="myengine", executable="myengine.exe"),
        ]

    def get_handler(self) -> Callable:
        """Return the step handler function."""
        from .handler import myengine_handler
        return myengine_handler

    def get_recipe_class(self) -> type:
        """Return the recipe class for input staging."""
        from .recipe import MyEngineRecipe
        return MyEngineRecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return GEN→SPEC mapping. Empty dict if no generalized steps."""
        return {"GEN_SCF": "myengine_scf"}
```

### 2.3 Minimal Complete Example

```python
# src/quantumvitas/drivers/myengine/driver.py

from quantumvitas.core.driver_protocol import StepTypeSpec

class MyEngineDriver:
    """Smallest valid driver implementation."""

    @property
    def engine_family(self) -> str:
        return "myengine"

    @property
    def display_name(self) -> str:
        return "My Engine"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(id="myengine_scf", engine="myengine", executable="myengine"),
        ]

    def get_handler(self):
        from .handler import handler
        return handler

    def get_recipe_class(self):
        from .recipe import MyEngineRecipe
        return MyEngineRecipe

    def get_materialization_map(self) -> dict[str, str]:
        return {"GEN_SCF": "myengine_scf"}
```

**Line count**: ~25 lines. This is the absolute minimum.

---

## 3. SHOULD Interface (Recommended, Kernel-Defaulted)

These methods have **kernel-provided defaults**. Drivers override only what they need.

### 3.1 Available SHOULD Methods

| Method | Default | When to Override |
|--------|---------|------------------|
| `get_workdir_policy()` | `ISOLATED` | VASP: CLEANUP; QE: SHARED |
| `get_capabilities()` | `set()` | For UI hints, feature gating |
| `supports_incremental_skip(step_type)` | `True` | MD steps should return `False` |
| `get_preflight_requirements(step)` | `[]` | VASP: CHGCAR/WAVECAR checks |
| `classify_error(stderr, exit_code)` | `UNKNOWN` | Better error messages |

### 3.2 Default Implementations via BaseEngineDriver

```python
# src/quantumvitas/core/driver_protocol.py

class BaseEngineDriver:
    """Optional base class providing SHOULD/PLUGIN defaults."""

    # ─────────────────────────────────────────────────────────────
    # SHOULD defaults
    # ─────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """Default: isolated per-step workdir, no cleanup."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """Default: no capabilities declared."""
        return set()

    def supports_incremental_skip(self, step_type: str) -> bool:
        """Default: all steps can be skipped."""
        return True

    def get_preflight_requirements(self, step: "Step") -> list["PreflightRequirement"]:
        """Default: no preflight checks."""
        return []

    def classify_error(self, stderr: str, exit_code: int) -> "ErrorClass":
        """Default: unknown error class."""
        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────
    # PLUGIN defaults
    # ─────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """Default: no artifact patterns."""
        return {}

    def find_latest_artifact(self, workdir: "Path", artifact_type: str) -> "Path | None":
        """Default: no artifact discovery."""
        return None

    def resolve_executable(self, step_type: str) -> "Path | None":
        """Default: use PATH lookup."""
        return None
```

### 3.3 Using BaseEngineDriver

```python
# src/quantumvitas/drivers/vasp/driver.py

from quantumvitas.core.driver_protocol import BaseEngineDriver, WorkdirPolicy

class VASPDriver(BaseEngineDriver):
    """VASP driver inheriting defaults."""

    # MUST (required)
    @property
    def engine_family(self) -> str:
        return "vasp"

    # ... other MUST methods ...

    # SHOULD (override only what differs from default)
    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.CLEANUP  # VASP cleans workdir

    def supports_incremental_skip(self, step_type: str) -> bool:
        return step_type != "vasp_md"  # MD can't be skipped

    # Everything else uses BaseEngineDriver defaults
```

---

## 4. Capabilities Negotiation (Lightweight)

### 4.1 Capability Tags (String Set)

Capabilities are declared as a set of string tags:

```python
def get_capabilities(self) -> set[str]:
    return {"scf", "relax", "md", "periodic", "mpi"}
```

### 4.2 Standard Tags

| Category | Tags |
|----------|------|
| Calculation types | `scf`, `relax`, `md`, `bands`, `dos`, `phonon`, `neb` |
| Structure types | `periodic`, `molecular`, `surface` |
| Parallelism | `mpi`, `openmp`, `gpu` |
| Continuation | `restart`, `wfn_continuation`, `charge_continuation` |

### 4.3 Querying Capabilities

```python
# Kernel code (example)
driver = DriverRegistry.get_driver("vasp")
caps = driver.get_capabilities()

if "md" in caps:
    # Engine supports MD
    pass

if "mpi" in caps:
    # Can use MPI parallelism
    pass
```

### 4.4 Why String Set (Not Dataclass)

**Chosen**: `set[str]`
**Rejected**: `EngineCapabilities` dataclass with 30 boolean fields

Rationale:
- Adding new capability doesn't require protocol change
- Engines declare only what they support
- Easy to extend with engine-specific tags (e.g., `vasp_gpu6`)
- No boilerplate for simple engines

---

## 5. Policies (Kernel-Applied)

### 5.1 WorkdirPolicy

```python
from enum import Enum

class WorkdirPolicy(Enum):
    ISOLATED = "isolated"   # Per-step workdir, no cleanup (default)
    CLEANUP = "cleanup"     # rm -rf before each step (VASP)
    SHARED = "shared"       # Shared outdir with prefixes (QE)
```

**Kernel applies policy**:
```python
# In handler dispatch (kernel side)
def prepare_workdir(step, driver):
    policy = driver.get_workdir_policy()

    if policy == WorkdirPolicy.CLEANUP:
        if workdir.exists():
            shutil.rmtree(workdir)
        workdir.mkdir(parents=True)
    elif policy == WorkdirPolicy.ISOLATED:
        workdir.mkdir(parents=True, exist_ok=True)
    elif policy == WorkdirPolicy.SHARED:
        # QE-specific handling (deferred to QE migration)
        pass
```

### 5.2 Incremental Skip Policy

```python
# Driver declares
def supports_incremental_skip(self, step_type: str) -> bool:
    # MD steps should always run when targeted
    if step_type.endswith("_md"):
        return False
    return True
```

**Kernel checks before skipping**:
```python
# In step execution (kernel side)
def should_skip_step(step, driver):
    if not driver.supports_incremental_skip(step.step_type):
        return False  # Never skip
    # ... existing skip logic ...
```

---

## 6. Driver Bundle Directory Structure

### 6.1 Minimal Structure

```
src/quantumvitas/drivers/myengine/
├── __init__.py      # Registration (REQUIRED)
├── driver.py        # Driver class (REQUIRED)
├── handler.py       # Handler function (REQUIRED)
└── recipe.py        # Recipe class (REQUIRED)
```

### 6.2 Full Structure (With Optional Components)

```
src/quantumvitas/drivers/vasp/
├── __init__.py      # Registration
├── driver.py        # VASPDriver class
├── handler.py       # vasp_step_handler
├── recipe.py        # VASPRecipe
├── staging.py       # Input staging utilities (moved from execution/)
├── reference.py     # CHGCAR/WAVECAR resolution (moved from execution/)
├── parser.py        # Output parsing (optional)
└── resolver.py      # Executable discovery (optional)
```

### 6.3 Registration Pattern

```python
# src/quantumvitas/drivers/vasp/__init__.py

"""VASP driver bundle."""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import VASPDriver

# Register at import time
DriverRegistry.register(VASPDriver())
```

---

## 7. Avoiding Over-Abstraction

### 7.1 What We DON'T Do

| Anti-Pattern | Why Avoided |
|--------------|-------------|
| Abstract factory for handlers | Overkill; direct function return is fine |
| Plugin interface for parsers | Not needed; internal to driver |
| Capability negotiation protocol | String set is simpler |
| Dependency injection | Drivers instantiate their own components |
| Configuration schema | Driver-specific; no kernel abstraction |

### 7.2 Simplicity Guidelines

1. **No intermediate abstractions**: Driver → Handler, not Driver → Factory → Handler
2. **No registration ceremony**: Single `DriverRegistry.register()` call
3. **No configuration files**: Driver declares everything in code
4. **No plugin discovery**: Drivers are imported, not discovered at runtime
5. **No version negotiation**: API version is validated at registration

---

## 8. Migration Path for Existing Code

### 8.1 Moving Handler to Driver

**Before** (in `handlers.py`):
```python
def vasp_step_handler(job: Job, context: StepContext) -> JobResult:
    # ... 150 lines of VASP-specific code ...
```

**After** (in `drivers/vasp/handler.py`):
```python
# EXACT SAME CODE, just moved
def vasp_step_handler(job: Job, context: StepContext) -> JobResult:
    # ... same 150 lines ...
```

**No refactoring required**. Just move the function.

### 8.2 Moving Recipe to Driver

**Before** (in `recipes.py`):
```python
class VASPRecipe(BaseRecipe):
    # ... 100 lines ...
```

**After** (in `drivers/vasp/recipe.py`):
```python
# EXACT SAME CODE, just moved
class VASPRecipe(BaseRecipe):
    # ... same 100 lines ...
```

**No refactoring required**. Just move the class.

### 8.3 Creating Driver Class

**New file** (`drivers/vasp/driver.py`):
```python
from quantumvitas.core.driver_protocol import BaseEngineDriver, StepTypeSpec, WorkdirPolicy

class VASPDriver(BaseEngineDriver):
    @property
    def engine_family(self) -> str:
        return "vasp"

    @property
    def display_name(self) -> str:
        return "VASP"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        # Copy from workflow/registry.py VASP entries
        return [
            StepTypeSpec(id="vasp_scf", engine="vasp", executable="vasp_std"),
            StepTypeSpec(id="vasp_relax", engine="vasp", executable="vasp_std"),
            StepTypeSpec(id="vasp_md", engine="vasp", executable="vasp_std"),
            StepTypeSpec(id="vasp_bands", engine="vasp", executable="vasp_std"),
            StepTypeSpec(id="vasp_dos", engine="vasp", executable="vasp_std"),
        ]

    def get_handler(self):
        from .handler import vasp_step_handler
        return vasp_step_handler

    def get_recipe_class(self):
        from .recipe import VASPRecipe
        return VASPRecipe

    def get_materialization_map(self) -> dict[str, str]:
        # Copy from workflow/generalized_steps.py VASP entries
        return {
            "GEN_SCF": "vasp_scf",
            "GEN_RELAX": "vasp_relax",
            "GEN_MD": "vasp_md",
        }

    # Override only non-default SHOULD methods
    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.CLEANUP

    def supports_incremental_skip(self, step_type: str) -> bool:
        return step_type != "vasp_md"
```

**Effort**: ~40 lines of boilerplate wrapping existing code.

---

## 9. Validation at Registration

### 9.1 Kernel Validates

| Check | Error |
|-------|-------|
| `engine_family` non-empty | `InvalidDriverError` |
| `engine_family` unique | `DuplicateEngineError` |
| `driver_api_version` valid semver | `InvalidVersionError` |
| `driver_api_version` major == 1 | `IncompatibleDriverError` |
| `get_step_type_specs()` non-empty | `NoStepTypesError` |
| Each step type unique | `DuplicateStepTypeError` |
| Each step type's engine matches driver | `EnginesMismatchError` |

### 9.2 Validation Code

```python
# In DriverRegistry.register()
def _validate_driver(driver: EngineDriver) -> None:
    # Identity validation
    family = driver.engine_family
    if not family or not isinstance(family, str):
        raise InvalidDriverError("engine_family must be non-empty string")

    # Version validation
    version = driver.driver_api_version
    try:
        major, minor, patch = map(int, version.split("."))
    except ValueError:
        raise InvalidVersionError(f"Invalid version format: {version}")

    if major != 1:
        raise IncompatibleDriverError(
            f"Driver requires API v{major}.x but kernel supports v1.x"
        )

    # Step type validation
    specs = driver.get_step_type_specs()
    if not specs:
        raise NoStepTypesError(f"Driver {family} declares no step types")

    for spec in specs:
        if spec.engine != family:
            raise EnginesMismatchError(
                f"Step type {spec.id} declares engine '{spec.engine}' "
                f"but driver is '{family}'"
            )
```
