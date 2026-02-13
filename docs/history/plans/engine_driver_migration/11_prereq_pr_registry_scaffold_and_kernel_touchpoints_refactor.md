# Prerequisite PR 2: Registry Scaffold and Kernel Touchpoints Refactor

**PR Title**: `feat: Add DriverRegistry and refactor kernel to use registry-based dispatch`

**Priority**: MUST complete after PR 1 (Remove Fallbacks), before any engine migration

**Dependencies**: PR 1 merged (hard errors for unknown types)

---

## 1. Objective

Create the DriverRegistry infrastructure and refactor kernel touchpoints to use registry-based dispatch instead of hardcoded mappings. After this PR:

1. `DriverRegistry` exists and is functional
2. All routing goes through the registry
3. QE is registered as a "legacy driver" (minimal shim)
4. Kernel code no longer has hardcoded engine lists
5. Gate 1 tests pass

---

## 2. Files to Create

| File | Purpose | Lines (est.) |
|------|---------|--------------|
| `src/quantumvitas/core/driver_protocol.py` | Protocol + BaseEngineDriver | ~200 |
| `src/quantumvitas/core/driver_registry.py` | DriverRegistry singleton | ~250 |
| `src/quantumvitas/drivers/__init__.py` | Driver auto-registration | ~30 |
| `src/quantumvitas/drivers/qe_shim/__init__.py` | QE legacy shim | ~80 |
| `tests/gates/test_registry_routing.py` | Gate 1 tests | ~150 |

## 3. Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/quantumvitas/execution/handlers.py` | Use registry for handler dispatch | HIGH |
| `src/quantumvitas/execution/recipes.py` | Use registry for recipe dispatch | HIGH |
| `src/quantumvitas/workflow/generalized_steps.py` | Use registry for materialization | MEDIUM |
| `src/quantumvitas/calculation/structure_steps.py` | Use registry for step type queries | MEDIUM |
| `src/quantumvitas/calculation/step_done.py` | Use registry for step type queries | MEDIUM |
| `src/quantumvitas/core/calc_identity.py` | Use registry for engine inference | MEDIUM |

---

## 4. Step-by-Step Procedure

### Step 1: Create driver_protocol.py

**Create file**: `src/quantumvitas/core/driver_protocol.py`

```python
"""Engine driver protocol and base class.

This module defines the interface that all engine drivers must implement,
plus a base class providing sensible defaults for optional methods.
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quantumvitas.core.job import Job
    from quantumvitas.core.step_context import StepContext
    from quantumvitas.core.job_result import JobResult


class WorkdirPolicy(Enum):
    """Workdir management policy for engine handlers."""

    ISOLATED = "isolated"   # Per-step workdir, no cleanup (default)
    CLEANUP = "cleanup"     # rm -rf before each step (VASP)
    SHARED = "shared"       # Shared outdir with prefixes (QE)


class ErrorClass(Enum):
    """Classification of execution errors for reporting."""

    UNKNOWN = "unknown"
    CONVERGENCE = "convergence"
    MEMORY = "memory"
    TIMEOUT = "timeout"
    INPUT_ERROR = "input_error"
    MISSING_FILE = "missing_file"
    LICENSE = "license"
    EXECUTABLE_NOT_FOUND = "executable_not_found"


@dataclass(frozen=True)
class StepTypeSpec:
    """Specification for a step type.

    This dataclass defines all properties of a step type that the kernel
    needs to know for routing and execution.
    """

    id: str                          # Unique step type identifier (e.g., "vasp_scf")
    engine: str                      # Engine family (e.g., "vasp")
    executable: str                  # Default executable name (e.g., "vasp_std")
    description: str = ""            # Human-readable description
    category: str = "calculation"    # Category: calculation, postprocess, utility
    supports_restart: bool = True    # Whether step supports restart from checkpoint
    mpi_aware: bool = True           # Whether step can use MPI

    def __post_init__(self):
        if not self.id:
            raise ValueError("StepTypeSpec.id cannot be empty")
        if not self.engine:
            raise ValueError("StepTypeSpec.engine cannot be empty")
        if not self.id.startswith(f"{self.engine}_") and self.id not in self._allowed_special_ids():
            raise ValueError(
                f"StepTypeSpec.id '{self.id}' must start with engine prefix '{self.engine}_'"
            )

    def _allowed_special_ids(self) -> set[str]:
        """IDs that don't follow the prefix convention."""
        return {"w90_preproc", "w90_run"}  # Wannier90 legacy names


@dataclass
class PreflightRequirement:
    """A requirement that must be satisfied before step execution."""

    artifact_type: str              # e.g., "CHGCAR", "WAVECAR"
    source_step: str | None = None  # Step that produces it (None = auto-resolve)
    required: bool = True           # False = optional optimization
    description: str = ""           # Human-readable description


@runtime_checkable
class EngineDriver(Protocol):
    """Protocol defining the required interface for engine drivers.

    All engine drivers MUST implement these methods/properties.
    This is a Protocol, so drivers don't need to inherit from it,
    but they must structurally conform to this interface.
    """

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Properties (3 required)
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        """Unique engine identifier (e.g., 'vasp', 'orca').

        This is the canonical name used throughout the system.
        Must be lowercase, alphanumeric with underscores only.
        """
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name for UI/logs (e.g., 'VASP', 'ORCA')."""
        ...

    @property
    def driver_api_version(self) -> str:
        """Semver string (e.g., '1.0.0').

        Kernel validates major version compatibility at registration.
        Current kernel requires major version 1.
        """
        ...

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Methods (4 required)
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return all step types this driver handles.

        Each StepTypeSpec must have engine matching self.engine_family.
        """
        ...

    def get_handler(self) -> Callable[["Job", "StepContext"], "JobResult"]:
        """Return the step handler function.

        The handler is called for each step execution.
        """
        ...

    def get_recipe_class(self) -> type:
        """Return the recipe class for input staging.

        Recipe class must inherit from BaseRecipe.
        """
        ...

    def get_materialization_map(self) -> dict[str, str]:
        """Return GEN→SPEC mapping for generalized steps.

        Keys are generalized types (e.g., 'GEN_SCF').
        Values are engine-specific types (e.g., 'vasp_scf').
        Return empty dict if engine doesn't support generalized steps.
        """
        ...


class BaseEngineDriver:
    """Base class providing sensible defaults for optional driver methods.

    Drivers can inherit from this class to get default implementations
    of SHOULD and PLUGIN methods. Only MUST methods need to be overridden.

    This is an optional convenience - drivers can implement EngineDriver
    protocol directly without inheriting from this class.
    """

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Methods with sensible defaults
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """Default: isolated per-step workdir, no cleanup."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """Default: no capabilities declared.

        Override to declare engine capabilities like:
        - Calculation types: 'scf', 'relax', 'md', 'bands', 'dos'
        - Structure types: 'periodic', 'molecular', 'surface'
        - Parallelism: 'mpi', 'openmp', 'gpu'
        """
        return set()

    def supports_incremental_skip(self, step_type: str) -> bool:
        """Default: all steps can be skipped if already done.

        Override to return False for steps that should always run
        (e.g., MD steps where continuation matters).
        """
        return True

    def get_preflight_requirements(self, step: Any) -> list[PreflightRequirement]:
        """Default: no preflight checks.

        Override to declare requirements like CHGCAR/WAVECAR for VASP.
        """
        return []

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Default: unknown error class.

        Override to parse stderr and classify errors for better reporting.
        """
        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """Default: no artifact patterns.

        Override to declare output artifact patterns like:
        {'CHGCAR': 'CHGCAR*', 'WAVECAR': 'WAVECAR'}
        """
        return {}

    def find_latest_artifact(self, workdir: Path, artifact_type: str) -> Path | None:
        """Default: no artifact discovery.

        Override to implement artifact resolution logic.
        """
        return None

    def resolve_executable(self, step_type: str) -> Path | None:
        """Default: use PATH lookup.

        Override to implement custom executable resolution.
        """
        return None
```

**Validation**: File compiles, classes can be instantiated

### Step 2: Create driver_registry.py

**Create file**: `src/quantumvitas/core/driver_registry.py`

```python
"""Driver registry for engine-to-driver mapping.

This module provides the central registry that maps:
- Engine families to driver instances
- Step types to their specifications
- Generalized types to engine-specific types

The registry is a singleton that drivers register with at import time.
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import TYPE_CHECKING, Callable

from quantumvitas.core.driver_exceptions import (
    DuplicateEngineError,
    DuplicateStepTypeError,
    EnginesMismatchError,
    IncompatibleDriverError,
    InvalidDriverError,
    InvalidVersionError,
    NoStepTypesError,
    UnknownEngineError,
    UnknownMaterializationError,
    UnknownStepTypeError,
)
from quantumvitas.core.driver_protocol import EngineDriver, StepTypeSpec

if TYPE_CHECKING:
    from quantumvitas.core.job import Job
    from quantumvitas.core.job_result import JobResult
    from quantumvitas.core.step_context import StepContext

logger = logging.getLogger(__name__)

# Current kernel API version
KERNEL_API_VERSION = "1.0.0"


class DriverRegistry:
    """Singleton registry for engine drivers.

    Usage:
        # Registration (at driver import time)
        DriverRegistry.register(MyEngineDriver())

        # Lookup
        driver = DriverRegistry.get_driver("vasp")
        handler = DriverRegistry.get_handler("vasp_scf")
        spec = DriverRegistry.get_step_type_spec("vasp_scf")
    """

    _instance: DriverRegistry | None = None
    _lock = Lock()

    def __new__(cls) -> DriverRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize registry state."""
        self._drivers: dict[str, EngineDriver] = {}
        self._step_types: dict[str, StepTypeSpec] = {}
        self._step_to_engine: dict[str, str] = {}
        self._materialization_maps: dict[str, dict[str, str]] = {}
        self._frozen = False

    @classmethod
    def get_instance(cls) -> DriverRegistry:
        """Get the singleton registry instance."""
        return cls()

    @classmethod
    def register(cls, driver: EngineDriver) -> None:
        """Register a driver with the registry.

        Args:
            driver: Driver instance implementing EngineDriver protocol

        Raises:
            InvalidDriverError: If driver doesn't implement required interface
            DuplicateEngineError: If engine family already registered
            InvalidVersionError: If version format is invalid
            IncompatibleDriverError: If API version incompatible
            NoStepTypesError: If driver declares no step types
            DuplicateStepTypeError: If step type already registered
            EnginesMismatchError: If step type engine doesn't match driver
        """
        instance = cls.get_instance()
        instance._register(driver)

    def _register(self, driver: EngineDriver) -> None:
        """Internal registration logic."""
        if self._frozen:
            raise RuntimeError("Registry is frozen, cannot register new drivers")

        # Validate driver implements protocol
        self._validate_driver(driver)

        family = driver.engine_family

        # Check for duplicate registration
        if family in self._drivers:
            raise DuplicateEngineError(
                f"Engine '{family}' already registered by {type(self._drivers[family]).__name__}"
            )

        # Register driver
        self._drivers[family] = driver
        logger.info(f"Registered driver: {driver.display_name} ({family})")

        # Register step types
        for spec in driver.get_step_type_specs():
            if spec.id in self._step_types:
                raise DuplicateStepTypeError(
                    f"Step type '{spec.id}' already registered by engine "
                    f"'{self._step_to_engine[spec.id]}'"
                )
            self._step_types[spec.id] = spec
            self._step_to_engine[spec.id] = family
            logger.debug(f"  Registered step type: {spec.id}")

        # Register materialization map
        mat_map = driver.get_materialization_map()
        if mat_map:
            self._materialization_maps[family] = mat_map
            logger.debug(f"  Registered {len(mat_map)} materialization mappings")

    def _validate_driver(self, driver: EngineDriver) -> None:
        """Validate driver conforms to protocol."""
        # Check required properties
        family = driver.engine_family
        if not family or not isinstance(family, str):
            raise InvalidDriverError("engine_family must be non-empty string")

        if not family.replace("_", "").isalnum() or not family.islower():
            raise InvalidDriverError(
                f"engine_family '{family}' must be lowercase alphanumeric with underscores"
            )

        display = driver.display_name
        if not display or not isinstance(display, str):
            raise InvalidDriverError("display_name must be non-empty string")

        # Validate version
        version = driver.driver_api_version
        try:
            parts = version.split(".")
            if len(parts) != 3:
                raise ValueError("Must have 3 parts")
            major, minor, patch = map(int, parts)
        except (ValueError, AttributeError) as e:
            raise InvalidVersionError(f"Invalid version format '{version}': {e}")

        # Check API compatibility
        kernel_major = int(KERNEL_API_VERSION.split(".")[0])
        if major != kernel_major:
            raise IncompatibleDriverError(
                f"Driver requires API v{major}.x but kernel supports v{kernel_major}.x"
            )

        # Validate step types
        specs = driver.get_step_type_specs()
        if not specs:
            raise NoStepTypesError(f"Driver {family} declares no step types")

        for spec in specs:
            if spec.engine != family:
                raise EnginesMismatchError(
                    f"Step type '{spec.id}' declares engine '{spec.engine}' "
                    f"but driver is '{family}'"
                )

    @classmethod
    def get_driver(cls, engine_family: str) -> EngineDriver:
        """Get driver by engine family.

        Args:
            engine_family: Engine identifier (e.g., 'vasp')

        Returns:
            Driver instance

        Raises:
            UnknownEngineError: If engine not registered
        """
        instance = cls.get_instance()
        if engine_family not in instance._drivers:
            raise UnknownEngineError(engine_family, list(instance._drivers.keys()))
        return instance._drivers[engine_family]

    @classmethod
    def get_handler(cls, step_type: str) -> Callable[["Job", "StepContext"], "JobResult"]:
        """Get handler for step type.

        Args:
            step_type: Step type identifier (e.g., 'vasp_scf')

        Returns:
            Handler function

        Raises:
            UnknownStepTypeError: If step type not registered
        """
        instance = cls.get_instance()
        if step_type not in instance._step_to_engine:
            raise UnknownStepTypeError(step_type, list(instance._step_types.keys()))

        engine = instance._step_to_engine[step_type]
        driver = instance._drivers[engine]
        return driver.get_handler()

    @classmethod
    def get_recipe_class(cls, engine_family: str) -> type:
        """Get recipe class for engine.

        Args:
            engine_family: Engine identifier (e.g., 'vasp')

        Returns:
            Recipe class

        Raises:
            UnknownEngineError: If engine not registered
        """
        driver = cls.get_driver(engine_family)
        return driver.get_recipe_class()

    @classmethod
    def get_step_type_spec(cls, step_type: str) -> StepTypeSpec:
        """Get specification for step type.

        Args:
            step_type: Step type identifier (e.g., 'vasp_scf')

        Returns:
            StepTypeSpec instance

        Raises:
            UnknownStepTypeError: If step type not registered
        """
        instance = cls.get_instance()
        if step_type not in instance._step_types:
            raise UnknownStepTypeError(step_type, list(instance._step_types.keys()))
        return instance._step_types[step_type]

    @classmethod
    def get_engine_for_step_type(cls, step_type: str) -> str:
        """Get engine family for step type.

        Args:
            step_type: Step type identifier (e.g., 'vasp_scf')

        Returns:
            Engine family string

        Raises:
            UnknownStepTypeError: If step type not registered
        """
        instance = cls.get_instance()
        if step_type not in instance._step_to_engine:
            raise UnknownStepTypeError(step_type, list(instance._step_types.keys()))
        return instance._step_to_engine[step_type]

    @classmethod
    def materialize_step_type(cls, engine_family: str, gen_type: str) -> str:
        """Materialize generalized type to engine-specific type.

        Args:
            engine_family: Engine identifier (e.g., 'vasp')
            gen_type: Generalized type (e.g., 'GEN_SCF')

        Returns:
            Engine-specific step type (e.g., 'vasp_scf')

        Raises:
            UnknownEngineError: If engine not registered
            UnknownMaterializationError: If no mapping exists
        """
        instance = cls.get_instance()

        if engine_family not in instance._drivers:
            raise UnknownEngineError(engine_family, list(instance._drivers.keys()))

        mat_map = instance._materialization_maps.get(engine_family, {})
        if gen_type not in mat_map:
            raise UnknownMaterializationError(
                engine_family, gen_type, list(mat_map.keys())
            )

        return mat_map[gen_type]

    @classmethod
    def is_step_type_registered(cls, step_type: str) -> bool:
        """Check if step type is registered."""
        instance = cls.get_instance()
        return step_type in instance._step_types

    @classmethod
    def is_engine_registered(cls, engine_family: str) -> bool:
        """Check if engine is registered."""
        instance = cls.get_instance()
        return engine_family in instance._drivers

    @classmethod
    def get_all_step_types(cls) -> list[str]:
        """Get all registered step type IDs."""
        instance = cls.get_instance()
        return list(instance._step_types.keys())

    @classmethod
    def get_all_engines(cls) -> list[str]:
        """Get all registered engine families."""
        instance = cls.get_instance()
        return list(instance._drivers.keys())

    @classmethod
    def get_step_types_for_engine(cls, engine_family: str) -> list[str]:
        """Get all step types for an engine."""
        instance = cls.get_instance()
        return [
            st for st, eng in instance._step_to_engine.items()
            if eng == engine_family
        ]

    @classmethod
    def freeze(cls) -> None:
        """Freeze registry to prevent further registrations.

        Call after all drivers are loaded to catch late registrations.
        """
        instance = cls.get_instance()
        instance._frozen = True
        logger.info(
            f"Registry frozen: {len(instance._drivers)} engines, "
            f"{len(instance._step_types)} step types"
        )

    @classmethod
    def reset(cls) -> None:
        """Reset registry for testing purposes only.

        WARNING: Only use in tests. Never call in production code.
        """
        instance = cls.get_instance()
        instance._initialize()
        logger.warning("Registry reset - this should only happen in tests")
```

**Validation**: File compiles, registry can be instantiated

### Step 3: Update driver_exceptions.py

**File**: `src/quantumvitas/core/driver_exceptions.py`

**Add** the following exception classes (after the existing ones from PR 1):

```python
# Add after UnknownMaterializationError

class InvalidDriverError(DriverError):
    """Raised when driver doesn't implement required interface."""
    pass


class DuplicateEngineError(DriverError):
    """Raised when engine family is already registered."""
    pass


class DuplicateStepTypeError(DriverError):
    """Raised when step type is already registered."""
    pass


class InvalidVersionError(DriverError):
    """Raised when driver version format is invalid."""
    pass


class IncompatibleDriverError(DriverError):
    """Raised when driver API version is incompatible with kernel."""
    pass


class NoStepTypesError(DriverError):
    """Raised when driver declares no step types."""
    pass


class EnginesMismatchError(DriverError):
    """Raised when step type's engine doesn't match driver."""
    pass
```

### Step 4: Create drivers/__init__.py

**Create file**: `src/quantumvitas/drivers/__init__.py`

```python
"""Engine driver bundles.

This package contains all engine driver implementations.
Drivers are registered with the DriverRegistry at import time.

To ensure all drivers are registered, import this package:
    import quantumvitas.drivers

Or import specific drivers:
    from quantumvitas.drivers import vasp
"""

import logging

logger = logging.getLogger(__name__)

# Import all driver packages to trigger registration
# Each driver's __init__.py calls DriverRegistry.register()

# QE shim (legacy compatibility until QE is properly migrated)
from quantumvitas.drivers import qe_shim

# Note: Other drivers (vasp, orca, etc.) will be added as they are migrated
# They will be imported here to trigger auto-registration

logger.debug("Driver packages imported")
```

### Step 5: Create QE Legacy Shim

**Create directory**: `src/quantumvitas/drivers/qe_shim/`

**Create file**: `src/quantumvitas/drivers/qe_shim/__init__.py`

```python
"""QE legacy shim driver.

This is a minimal driver that wraps existing QE code in the driver interface.
It allows QE to work with the new registry system without full migration.

This shim will be replaced when QE is properly migrated in a future effort.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import BaseEngineDriver, StepTypeSpec, WorkdirPolicy


class QELegacyDriver(BaseEngineDriver):
    """Legacy QE driver wrapping existing implementation.

    This is a shim that:
    1. Registers QE step types with the registry
    2. Points to existing handler/recipe implementations
    3. Will be replaced by proper QE driver in future migration
    """

    @property
    def engine_family(self) -> str:
        return "qe"

    @property
    def display_name(self) -> str:
        return "Quantum ESPRESSO (Legacy)"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return QE step types.

        These are copied from the existing workflow/registry.py.
        """
        return [
            StepTypeSpec(id="qe_scf", engine="qe", executable="pw.x",
                        description="QE SCF calculation"),
            StepTypeSpec(id="qe_relax", engine="qe", executable="pw.x",
                        description="QE relaxation"),
            StepTypeSpec(id="qe_vc_relax", engine="qe", executable="pw.x",
                        description="QE variable-cell relaxation"),
            StepTypeSpec(id="qe_bands", engine="qe", executable="pw.x",
                        description="QE band structure"),
            StepTypeSpec(id="qe_nscf", engine="qe", executable="pw.x",
                        description="QE non-self-consistent calculation"),
            StepTypeSpec(id="qe_dos", engine="qe", executable="dos.x",
                        description="QE density of states"),
            StepTypeSpec(id="qe_pdos", engine="qe", executable="projwfc.x",
                        description="QE projected density of states"),
            StepTypeSpec(id="qe_ph", engine="qe", executable="ph.x",
                        description="QE phonon calculation"),
            StepTypeSpec(id="qe_q2r", engine="qe", executable="q2r.x",
                        description="QE q2r transformation"),
            StepTypeSpec(id="qe_matdyn", engine="qe", executable="matdyn.x",
                        description="QE matdyn calculation"),
            StepTypeSpec(id="qe_dynmat", engine="qe", executable="dynmat.x",
                        description="QE dynmat calculation"),
            StepTypeSpec(id="qe_pp", engine="qe", executable="pp.x",
                        description="QE post-processing"),
            StepTypeSpec(id="qe_plotband", engine="qe", executable="plotband.x",
                        description="QE band plotting"),
            StepTypeSpec(id="qe_hp", engine="qe", executable="hp.x",
                        description="QE Hubbard parameters"),
            # Wannier90 preprocessing (runs within QE context)
            StepTypeSpec(id="w90_preproc", engine="qe", executable="pw.x",
                        description="Wannier90 preprocessing"),
        ]

    def get_handler(self):
        """Return existing QE handler."""
        from quantumvitas.execution.handlers import qe_step_handler
        return qe_step_handler

    def get_recipe_class(self):
        """Return existing QE recipe."""
        from quantumvitas.execution.recipes import QERecipe
        return QERecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return QE materialization mappings."""
        return {
            "GEN_SCF": "qe_scf",
            "GEN_RELAX": "qe_relax",
            "GEN_BANDS": "qe_bands",
            "GEN_DOS": "qe_dos",
        }

    def get_workdir_policy(self) -> WorkdirPolicy:
        """QE uses shared outdir model."""
        return WorkdirPolicy.SHARED


# Register at import time
DriverRegistry.register(QELegacyDriver())
```

**Validation**: File compiles, QE driver registered

### Step 6: Create Gate 1 Tests

**Create file**: `tests/gates/test_registry_routing.py`

```python
"""Gate 1: Registry-based routing tests.

These tests verify that all routing goes through the registry
and that the registry provides correct mappings.
"""

import pytest
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import EngineDriver, StepTypeSpec
from quantumvitas.core.driver_exceptions import (
    UnknownEngineError,
    UnknownStepTypeError,
    UnknownMaterializationError,
    DuplicateEngineError,
    DuplicateStepTypeError,
)


class TestRegistryBasics:
    """Basic registry functionality tests."""

    def test_registry_is_singleton(self):
        """Registry should be a singleton."""
        r1 = DriverRegistry.get_instance()
        r2 = DriverRegistry.get_instance()
        assert r1 is r2

    def test_qe_shim_registered(self):
        """QE shim should be auto-registered."""
        # Import drivers to trigger registration
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("qe")
        driver = DriverRegistry.get_driver("qe")
        assert driver.engine_family == "qe"

    def test_unknown_engine_raises(self):
        """Unknown engine should raise UnknownEngineError."""
        with pytest.raises(UnknownEngineError) as exc_info:
            DriverRegistry.get_driver("nonexistent_engine_xyz")

        assert "nonexistent_engine_xyz" in str(exc_info.value)
        assert "qe" in str(exc_info.value)  # Should suggest available engines


class TestStepTypeRouting:
    """Step type to handler routing tests."""

    def test_known_step_type_returns_handler(self):
        """Known step type should return handler."""
        import quantumvitas.drivers

        handler = DriverRegistry.get_handler("qe_scf")
        assert callable(handler)

    def test_unknown_step_type_raises(self):
        """Unknown step type should raise UnknownStepTypeError."""
        with pytest.raises(UnknownStepTypeError) as exc_info:
            DriverRegistry.get_handler("totally_unknown_step_xyz")

        assert "totally_unknown_step_xyz" in str(exc_info.value)

    def test_step_type_spec_retrieval(self):
        """Should retrieve full StepTypeSpec for step type."""
        import quantumvitas.drivers

        spec = DriverRegistry.get_step_type_spec("qe_scf")
        assert spec.id == "qe_scf"
        assert spec.engine == "qe"
        assert spec.executable == "pw.x"

    def test_engine_for_step_type(self):
        """Should retrieve engine family for step type."""
        import quantumvitas.drivers

        engine = DriverRegistry.get_engine_for_step_type("qe_scf")
        assert engine == "qe"


class TestMaterialization:
    """Generalized to specific type materialization tests."""

    def test_materialize_known_type(self):
        """Known gen type should materialize to spec type."""
        import quantumvitas.drivers

        spec_type = DriverRegistry.materialize_step_type("qe", "GEN_SCF")
        assert spec_type == "qe_scf"

    def test_materialize_unknown_gen_type_raises(self):
        """Unknown gen type should raise UnknownMaterializationError."""
        import quantumvitas.drivers

        with pytest.raises(UnknownMaterializationError) as exc_info:
            DriverRegistry.materialize_step_type("qe", "GEN_NONEXISTENT")

        assert "GEN_NONEXISTENT" in str(exc_info.value)

    def test_materialize_unknown_engine_raises(self):
        """Unknown engine should raise UnknownEngineError."""
        with pytest.raises(UnknownEngineError):
            DriverRegistry.materialize_step_type("nonexistent", "GEN_SCF")


class TestRecipeRouting:
    """Recipe class routing tests."""

    def test_recipe_class_for_engine(self):
        """Should retrieve recipe class for engine."""
        import quantumvitas.drivers

        recipe_class = DriverRegistry.get_recipe_class("qe")
        assert recipe_class is not None
        assert hasattr(recipe_class, "stage")  # BaseRecipe method

    def test_recipe_class_unknown_engine_raises(self):
        """Unknown engine should raise UnknownEngineError."""
        with pytest.raises(UnknownEngineError):
            DriverRegistry.get_recipe_class("nonexistent_engine")


class TestDriverValidation:
    """Driver registration validation tests."""

    def setup_method(self):
        """Reset registry before each test."""
        DriverRegistry.reset()
        # Re-import to get QE shim back
        import importlib
        import quantumvitas.drivers
        importlib.reload(quantumvitas.drivers)

    def test_duplicate_engine_rejected(self):
        """Duplicate engine registration should raise."""
        # QE is already registered
        from quantumvitas.drivers.qe_shim import QELegacyDriver

        with pytest.raises(DuplicateEngineError):
            DriverRegistry.register(QELegacyDriver())

    def test_empty_engine_family_rejected(self):
        """Empty engine family should be rejected."""
        class BadDriver:
            engine_family = ""
            display_name = "Bad"
            driver_api_version = "1.0.0"

            def get_step_type_specs(self):
                return [StepTypeSpec(id="bad_scf", engine="bad", executable="bad")]

            def get_handler(self):
                return lambda j, c: None

            def get_recipe_class(self):
                return object

            def get_materialization_map(self):
                return {}

        from quantumvitas.core.driver_exceptions import InvalidDriverError
        with pytest.raises(InvalidDriverError):
            DriverRegistry.register(BadDriver())


class TestKernelIntegration:
    """Tests that kernel code uses registry."""

    def test_handlers_uses_registry(self):
        """handlers.py should use registry for dispatch."""
        from pathlib import Path
        source = Path("src/quantumvitas/execution/handlers.py").read_text()

        # After refactor, should import and use DriverRegistry
        assert "DriverRegistry" in source or "driver_registry" in source, (
            "handlers.py should use DriverRegistry for dispatch"
        )

    def test_recipes_uses_registry(self):
        """recipes.py should use registry for dispatch."""
        from pathlib import Path
        source = Path("src/quantumvitas/execution/recipes.py").read_text()

        # After refactor, should import and use DriverRegistry
        assert "DriverRegistry" in source or "driver_registry" in source, (
            "recipes.py should use DriverRegistry for dispatch"
        )
```

**Run tests**: `pytest tests/gates/test_registry_routing.py -v`

**Expected result**: Tests FAIL initially (kernel not yet refactored)

### Step 7: Refactor handlers.py

**File**: `src/quantumvitas/execution/handlers.py`

**Change 1**: Add registry import at top (after other imports):

```python
from quantumvitas.core.driver_registry import DriverRegistry
```

**Change 2**: Modify `create_handler_map()` function (around line 1312):

```python
# BEFORE:
def create_handler_map() -> dict[str, Callable]:
    """Create mapping of step types to handlers."""
    return {
        "qe_scf": qe_step_handler,
        "qe_relax": qe_step_handler,
        # ... 50+ hardcoded entries ...
        "vasp_scf": vasp_step_handler,
        # etc.
    }

# AFTER:
def create_handler_map() -> dict[str, Callable]:
    """Create mapping of step types to handlers.

    This now delegates to DriverRegistry for all registered drivers.
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    handler_map = {}
    for step_type in DriverRegistry.get_all_step_types():
        handler_map[step_type] = DriverRegistry.get_handler(step_type)

    return handler_map
```

**Change 3**: Add registry-based dispatch function:

```python
def get_handler_for_step(step_type: str) -> Callable:
    """Get handler for step type via registry.

    This is the preferred entry point for handler lookup.

    Args:
        step_type: Step type identifier

    Returns:
        Handler function

    Raises:
        UnknownStepTypeError: If step type not registered
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    return DriverRegistry.get_handler(step_type)
```

### Step 8: Refactor recipes.py

**File**: `src/quantumvitas/execution/recipes.py`

**Change 1**: Add registry import at top:

```python
from quantumvitas.core.driver_registry import DriverRegistry
```

**Change 2**: Modify `get_recipe_class()` function (around line 798):

```python
# BEFORE:
def get_recipe_class(engine_family: str) -> type[BaseRecipe]:
    """Get recipe class for engine family."""
    recipe_map = {
        "qe": QERecipe,
        "vasp": VASPRecipe,
        "orca": ORCARecipe,
        # ... hardcoded entries ...
    }
    if engine_family not in recipe_map:
        from quantumvitas.core.driver_exceptions import UnknownEngineError
        raise UnknownEngineError(engine_family, list(recipe_map.keys()))
    return recipe_map[engine_family]

# AFTER:
def get_recipe_class(engine_family: str) -> type[BaseRecipe]:
    """Get recipe class for engine family via registry.

    Args:
        engine_family: Engine identifier (e.g., 'vasp')

    Returns:
        Recipe class for engine

    Raises:
        UnknownEngineError: If engine not registered
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    return DriverRegistry.get_recipe_class(engine_family)
```

### Step 9: Refactor generalized_steps.py

**File**: `src/quantumvitas/workflow/generalized_steps.py`

**Change 1**: Add registry import:

```python
from quantumvitas.core.driver_registry import DriverRegistry
```

**Change 2**: Modify materialization logic (around line 61):

```python
# BEFORE:
MATERIALIZATION_MAP = {
    ("qe", "GEN_SCF"): "qe_scf",
    ("qe", "GEN_RELAX"): "qe_relax",
    ("vasp", "GEN_SCF"): "vasp_scf",
    # ... 30+ hardcoded entries ...
}

def materialize_step_type(engine: str, gen_type: str) -> str:
    """Materialize generalized type to engine-specific type."""
    key = (engine, gen_type)
    if key not in MATERIALIZATION_MAP:
        raise ValueError(f"No materialization for {key}")
    return MATERIALIZATION_MAP[key]

# AFTER:
def materialize_step_type(engine: str, gen_type: str) -> str:
    """Materialize generalized type to engine-specific type.

    This now delegates to DriverRegistry.

    Args:
        engine: Engine family (e.g., 'vasp')
        gen_type: Generalized type (e.g., 'GEN_SCF')

    Returns:
        Engine-specific step type

    Raises:
        UnknownMaterializationError: If no mapping exists
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    return DriverRegistry.materialize_step_type(engine, gen_type)


# Keep MATERIALIZATION_MAP for backward compatibility during transition
# This will be removed after all callers are updated
MATERIALIZATION_MAP = {}  # Populated dynamically from registry

def _populate_compat_map():
    """Populate compatibility map from registry."""
    import quantumvitas.drivers
    for engine in DriverRegistry.get_all_engines():
        try:
            driver = DriverRegistry.get_driver(engine)
            for gen_type, spec_type in driver.get_materialization_map().items():
                MATERIALIZATION_MAP[(engine, gen_type)] = spec_type
        except Exception:
            pass

# Populate on import
_populate_compat_map()
```

### Step 10: Refactor structure_steps.py

**File**: `src/quantumvitas/calculation/structure_steps.py`

**Change 1**: Add registry import:

```python
from quantumvitas.core.driver_registry import DriverRegistry
```

**Change 2**: Remove hardcoded step type sets (around lines 778-791):

```python
# BEFORE:
PYSCF_STEP_TYPES = {"pyscf_scf", "pyscf_opt", "pyscf_freq", ...}
ORCA_STEP_TYPES = {"orca_scf", "orca_opt", "orca_freq", ...}
LAMMPS_STEP_TYPES = {"lammps_minimize", "lammps_md", ...}
CP2K_STEP_TYPES = {"cp2k_scf", "cp2k_relax", ...}

def is_pyscf_step(step_type: str) -> bool:
    return step_type in PYSCF_STEP_TYPES

# AFTER:
def get_step_types_for_engine(engine: str) -> set[str]:
    """Get all step types for engine from registry."""
    import quantumvitas.drivers
    return set(DriverRegistry.get_step_types_for_engine(engine))

def is_pyscf_step(step_type: str) -> bool:
    """Check if step type belongs to PySCF."""
    import quantumvitas.drivers
    if not DriverRegistry.is_step_type_registered(step_type):
        return False
    return DriverRegistry.get_engine_for_step_type(step_type) == "pyscf"

def is_orca_step(step_type: str) -> bool:
    """Check if step type belongs to ORCA."""
    import quantumvitas.drivers
    if not DriverRegistry.is_step_type_registered(step_type):
        return False
    return DriverRegistry.get_engine_for_step_type(step_type) == "orca"

def is_lammps_step(step_type: str) -> bool:
    """Check if step type belongs to LAMMPS."""
    import quantumvitas.drivers
    if not DriverRegistry.is_step_type_registered(step_type):
        return False
    return DriverRegistry.get_engine_for_step_type(step_type) == "lammps"

def is_cp2k_step(step_type: str) -> bool:
    """Check if step type belongs to CP2K."""
    import quantumvitas.drivers
    if not DriverRegistry.is_step_type_registered(step_type):
        return False
    return DriverRegistry.get_engine_for_step_type(step_type) == "cp2k"

# Backward compatibility (deprecated, will be removed)
PYSCF_STEP_TYPES = property(lambda self: get_step_types_for_engine("pyscf"))
ORCA_STEP_TYPES = property(lambda self: get_step_types_for_engine("orca"))
LAMMPS_STEP_TYPES = property(lambda self: get_step_types_for_engine("lammps"))
CP2K_STEP_TYPES = property(lambda self: get_step_types_for_engine("cp2k"))
```

### Step 11: Refactor step_done.py

**File**: `src/quantumvitas/calculation/step_done.py`

**Change 1**: Add registry import:

```python
from quantumvitas.core.driver_registry import DriverRegistry
```

**Change 2**: Remove hardcoded step type sets (around lines 18, 161-162):

```python
# BEFORE:
VASP_STEP_TYPES = {"vasp_scf", "vasp_relax", "vasp_md", ...}
LAMMPS_STEP_TYPES = {"lammps_minimize", "lammps_md", ...}

def is_vasp_step(step_type: str) -> bool:
    return step_type in VASP_STEP_TYPES

# AFTER:
def is_vasp_step(step_type: str) -> bool:
    """Check if step type belongs to VASP."""
    import quantumvitas.drivers
    if not DriverRegistry.is_step_type_registered(step_type):
        return False
    return DriverRegistry.get_engine_for_step_type(step_type) == "vasp"

def is_lammps_step(step_type: str) -> bool:
    """Check if step type belongs to LAMMPS."""
    import quantumvitas.drivers
    if not DriverRegistry.is_step_type_registered(step_type):
        return False
    return DriverRegistry.get_engine_for_step_type(step_type) == "lammps"
```

### Step 12: Refactor calc_identity.py

**File**: `src/quantumvitas/core/calc_identity.py`

**Change 1**: Add registry import:

```python
from quantumvitas.core.driver_registry import DriverRegistry
```

**Change 2**: Modify `_infer_engine_family_from_machine_types()` (lines 78-115):

```python
# BEFORE (after PR 1 fix):
def _infer_engine_family_from_machine_types(machine_types: list[str]) -> str | None:
    """Infer engine family from step types."""
    families = set()
    for machine_type in machine_types:
        if machine_type.startswith("qe_") or machine_type in ("w90_preproc", "w90_run"):
            families.add("qe")
        elif machine_type.startswith("pyscf_"):
            families.add("pyscf")
        # ... more prefixes ...
        # else: Unknown type - do NOT add to families

    if len(families) == 1:
        return families.pop()
    return None

# AFTER (registry-based):
def _infer_engine_family_from_machine_types(machine_types: list[str]) -> str | None:
    """Infer engine family from step types using registry.

    Args:
        machine_types: List of step type identifiers

    Returns:
        Single engine family if all steps belong to one engine, else None
    """
    import quantumvitas.drivers

    families = set()
    for step_type in machine_types:
        if DriverRegistry.is_step_type_registered(step_type):
            engine = DriverRegistry.get_engine_for_step_type(step_type)
            families.add(engine)
        # Unknown step types are ignored - will fail at handler dispatch

    if len(families) == 1:
        return families.pop()

    # Mixed engines or no recognized step types
    return None
```

### Step 13: Run All Gate 1 Tests

```bash
pytest tests/gates/test_registry_routing.py -v
```

**Expected**: All tests PASS

### Step 14: Run Full Test Suite

```bash
pytest tests/ -v
```

**Expected**: All existing tests pass. If any fail:
1. Check if test relied on hardcoded behavior
2. Update test to use registry APIs
3. Document the change

---

## 5. Backward Compatibility Notes

### 5.1 Preserved APIs

These APIs continue to work (delegating to registry):

| API | Status |
|-----|--------|
| `create_handler_map()` | Works, builds map from registry |
| `get_recipe_class(engine)` | Works, delegates to registry |
| `materialize_step_type(engine, gen)` | Works, delegates to registry |
| `MATERIALIZATION_MAP` | Works, populated from registry |

### 5.2 Deprecated APIs (One Minor Version)

| API | Replacement | Removal |
|-----|-------------|---------|
| `PYSCF_STEP_TYPES` | `get_step_types_for_engine("pyscf")` | v2.x |
| `ORCA_STEP_TYPES` | `get_step_types_for_engine("orca")` | v2.x |
| `VASP_STEP_TYPES` | `get_step_types_for_engine("vasp")` | v2.x |
| Direct handler imports | `DriverRegistry.get_handler()` | v2.x |

---

## 6. PR Checklist

- [ ] `driver_protocol.py` created with Protocol + BaseEngineDriver
- [ ] `driver_registry.py` created with DriverRegistry singleton
- [ ] `driver_exceptions.py` updated with registration errors
- [ ] `drivers/__init__.py` created with auto-import
- [ ] `drivers/qe_shim/` created with QE legacy driver
- [ ] Gate 1 tests created and pass
- [ ] `handlers.py` refactored to use registry
- [ ] `recipes.py` refactored to use registry
- [ ] `generalized_steps.py` refactored to use registry
- [ ] `structure_steps.py` refactored to use registry
- [ ] `step_done.py` refactored to use registry
- [ ] `calc_identity.py` refactored to use registry
- [ ] Full test suite passes
- [ ] No regressions in CI

---

## 7. Definition of Done

1. DriverRegistry exists and is functional
2. QE shim is registered and working
3. All handler dispatch goes through registry
4. All recipe dispatch goes through registry
5. All materialization goes through registry
6. All step type queries use registry
7. No hardcoded engine lists in kernel files
8. Gate 1 tests pass
9. All existing tests pass
10. CI green

---

## 8. Risk Mitigation

### 8.1 High-Risk Changes

| Change | Risk | Mitigation |
|--------|------|------------|
| Handler dispatch refactor | May break execution | Keep original functions as wrappers |
| Recipe dispatch refactor | May break staging | Keep original function signature |
| Materialization refactor | May break GEN steps | Keep MATERIALIZATION_MAP as compat |

### 8.2 Rollback Strategy

If critical issues discovered after merge:

1. Registry changes are additive - can disable registry usage with feature flag
2. Keep wrapper functions that delegate to registry
3. Can revert to direct function calls if needed

### 8.3 Testing Strategy

1. Run full test suite before and after each file change
2. Run integration tests after all changes
3. Manual test: Create calculation, run with VASP/ORCA/PySCF step types
4. Verify CI passes on PR
