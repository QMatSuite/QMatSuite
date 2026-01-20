# Driver Model Specification

**Document Version**: 1.0
**Date**: 2026-01-20
**Status**: DESIGN PROPOSAL

---

## 1. Overview

This document specifies the **EngineDriver** protocol that all engine integrations must implement. The driver model provides:

1. **Explicit binding**: step_type → driver with no inference
2. **Capabilities declaration**: What each engine supports
3. **Versioned interface**: Breaking changes are manageable
4. **Concentrated registration**: All engine logic in one bundle

---

## 2. Core Interfaces

### 2.1 EngineDriver Protocol

```python
from typing import Protocol, Callable, Any
from pathlib import Path
from dataclasses import dataclass

class EngineDriver(Protocol):
    """
    Protocol that all engine drivers must implement.

    A driver is a concentrated bundle of engine-specific logic that
    registers with the kernel. The kernel never contains engine-specific
    code - all such logic lives in drivers.
    """

    # =========================================================================
    # Identity
    # =========================================================================

    @property
    def engine_family(self) -> str:
        """
        Unique identifier for this engine family.

        Examples: "qe", "vasp", "orca", "pyscf", "lammps", "cp2k", "w90"
        """
        ...

    @property
    def engine_display_name(self) -> str:
        """Human-readable name for UI/logs. E.g., 'Quantum ESPRESSO'"""
        ...

    @property
    def driver_api_version(self) -> str:
        """
        Semantic version of the driver API this driver implements.

        Format: "MAJOR.MINOR.PATCH"
        - MAJOR: Breaking changes to protocol
        - MINOR: New optional capabilities
        - PATCH: Bug fixes
        """
        ...

    # =========================================================================
    # Registration
    # =========================================================================

    def get_step_type_specs(self) -> list["StepTypeSpec"]:
        """
        Return all step types this driver handles.

        The kernel registers these in STEP_TYPE_REGISTRY.
        Each spec must have unique `id` and `machine_type`.
        """
        ...

    def get_recipe_class(self) -> type["BaseRecipe"]:
        """Return the recipe class for this engine."""
        ...

    def get_handler(self) -> Callable[["Job", "StepContext"], "JobResult"]:
        """Return the step handler function for this engine."""
        ...

    def get_materialization_map(self) -> dict[str, str]:
        """
        Return mapping from generalized step types to machine step types.

        Keys: Generalized types like "GEN_SCF", "GEN_RELAX", "GEN_MD"
        Values: Machine step types like "pw_scf", "vasp_relax"
        """
        ...

    # =========================================================================
    # Capabilities
    # =========================================================================

    def get_capabilities(self) -> "EngineCapabilities":
        """Declare what this engine supports."""
        ...

    def get_preflight_requirements(
        self, step: "Step"
    ) -> list["PreflightRequirement"]:
        """
        Return preflight requirements for a given step.

        Called before step execution to validate required artifacts exist.
        """
        ...

    # =========================================================================
    # Artifacts
    # =========================================================================

    def get_artifact_patterns(self) -> dict[str, str]:
        """
        Return glob patterns for artifact types.

        Keys: Artifact types like "restart", "wfn", "trajectory"
        Values: Glob patterns like "*.restart", "cp2k_calc-RESTART.wfn"
        """
        ...

    def find_latest_artifact(
        self, workdir: Path, artifact_type: str
    ) -> Path | None:
        """
        Find the latest artifact of given type in workdir.

        Uses mtime-based selection when multiple matches exist.
        Returns None if no matching artifact found.
        """
        ...

    # =========================================================================
    # Workdir Policy
    # =========================================================================

    def get_workdir_policy(self) -> "WorkdirPolicy":
        """
        Declare workdir handling policy.

        - CLEANUP: rm -rf workdir before each step (VASP pattern)
        - ACCUMULATE: keep artifacts across steps (LAMMPS/CP2K pattern)
        - SHARED: shared outdir model (QE pattern)
        """
        ...

    # =========================================================================
    # Done/Skip Policy
    # =========================================================================

    def get_done_policy_class(self) -> type["DonePolicy"]:
        """Return the done policy class for determining step completion."""
        ...

    def supports_incremental_skip(self, step_type: str) -> bool:
        """
        Whether a step type supports incremental skip.

        MD steps typically return False (always execute when targeted).
        """
        ...

    # =========================================================================
    # Executable Discovery
    # =========================================================================

    def get_executable_resolver(self) -> "ExecutableResolver":
        """Return resolver for finding engine binary."""
        ...
```

### 2.2 EngineCapabilities Dataclass

```python
@dataclass(frozen=True)
class EngineCapabilities:
    """Declaration of what an engine supports."""

    # Calculation types
    supports_scf: bool = False
    supports_relax: bool = False
    supports_md: bool = False
    supports_bands: bool = False
    supports_dos: bool = False
    supports_phonon: bool = False
    supports_neb: bool = False

    # Continuation support
    supports_restart: bool = False
    supports_wfn_continuation: bool = False
    supports_charge_continuation: bool = False

    # Parallelism
    supports_mpi: bool = False
    supports_openmp: bool = False
    supports_gpu: bool = False

    # Structure types
    supports_periodic: bool = False
    supports_molecular: bool = False
    supports_surface: bool = False

    # Special features
    supports_spin_polarized: bool = False
    supports_soc: bool = False
    supports_dft_plus_u: bool = False
    supports_hybrid_functionals: bool = False
    supports_vdw_corrections: bool = False
```

### 2.3 WorkdirPolicy Enum

```python
from enum import Enum

class WorkdirPolicy(Enum):
    """Workdir handling policy for engine."""

    CLEANUP = "cleanup"
    """rm -rf workdir before each step. Used by VASP."""

    ACCUMULATE = "accumulate"
    """Keep artifacts across steps. Used by LAMMPS, CP2K."""

    SHARED = "shared"
    """Shared outdir with prefix namespacing. Used by QE."""
```

### 2.4 PreflightRequirement Dataclass

```python
@dataclass(frozen=True)
class PreflightRequirement:
    """Declaration of required artifact for preflight check."""

    artifact_type: str
    """Type of artifact: "restart", "wfn", "chgcar", etc."""

    pattern: str
    """Glob pattern to search for artifact."""

    source_step: str
    """Where to look: "predecessor" or specific step_ulid."""

    required: bool
    """If True, missing artifact raises PreflightError."""

    message: str
    """Error message template. Supports {pattern}, {source_dir} placeholders."""
```

### 2.5 StepTypeSpec (Existing, Unchanged)

```python
@dataclass(frozen=True)
class StepTypeSpec:
    """Specification for a step type."""

    id: str
    """Unique identifier, e.g., 'vasp_scf'."""

    machine_type: str
    """Machine-level type, often same as id."""

    engine: str
    """Engine family: 'qe', 'vasp', 'orca', etc."""

    executable: str
    """Executable name: 'pw.x', 'vasp_std', 'orca'."""

    description: str = ""
    """Human-readable description."""

    supports_incremental_skip: bool = True
    """Whether step supports incremental skip."""

    requires_structure: bool = True
    """Whether step requires input structure."""
```

---

## 3. Driver Registration

### 3.1 Kernel Driver Registry

```python
# src/quantumvitas/core/driver_registry.py

from typing import Dict
from .driver_protocol import EngineDriver

class DriverRegistry:
    """
    Central registry for engine drivers.

    Drivers register at import time. The kernel queries this
    registry instead of using hardcoded engine logic.
    """

    _drivers: Dict[str, EngineDriver] = {}
    _step_type_to_driver: Dict[str, EngineDriver] = {}

    @classmethod
    def register(cls, driver: EngineDriver) -> None:
        """
        Register an engine driver.

        Called by driver modules at import time.
        """
        family = driver.engine_family

        if family in cls._drivers:
            raise DriverAlreadyRegisteredError(
                f"Driver for '{family}' already registered"
            )

        # Validate API version compatibility
        cls._validate_api_version(driver)

        # Register driver
        cls._drivers[family] = driver

        # Register step types
        for spec in driver.get_step_type_specs():
            if spec.id in cls._step_type_to_driver:
                raise DuplicateStepTypeError(
                    f"Step type '{spec.id}' already registered by "
                    f"'{cls._step_type_to_driver[spec.id].engine_family}'"
                )
            cls._step_type_to_driver[spec.id] = driver

    @classmethod
    def get_driver(cls, engine_family: str) -> EngineDriver:
        """Get driver by engine family. Raises if not found."""
        if engine_family not in cls._drivers:
            raise UnknownEngineError(
                f"No driver registered for engine '{engine_family}'. "
                f"Available: {list(cls._drivers.keys())}"
            )
        return cls._drivers[engine_family]

    @classmethod
    def get_driver_for_step_type(cls, step_type: str) -> EngineDriver:
        """Get driver that handles a step type. Raises if not found."""
        if step_type not in cls._step_type_to_driver:
            raise UnknownStepTypeError(
                f"No driver registered for step type '{step_type}'. "
                f"Check spelling or ensure engine driver is installed."
            )
        return cls._step_type_to_driver[step_type]

    @classmethod
    def get_all_drivers(cls) -> Dict[str, EngineDriver]:
        """Get all registered drivers."""
        return cls._drivers.copy()

    @classmethod
    def _validate_api_version(cls, driver: EngineDriver) -> None:
        """Validate driver API version is compatible."""
        version = driver.driver_api_version
        major, minor, patch = map(int, version.split("."))

        # Current kernel supports API version 1.x
        SUPPORTED_MAJOR = 1
        if major != SUPPORTED_MAJOR:
            raise IncompatibleDriverError(
                f"Driver '{driver.engine_family}' requires API v{major}.x "
                f"but kernel supports v{SUPPORTED_MAJOR}.x"
            )
```

### 3.2 Driver Auto-Discovery

```python
# src/quantumvitas/drivers/__init__.py

"""
Engine driver auto-discovery.

Drivers are loaded from the `drivers/` directory at import time.
Each driver module must call DriverRegistry.register() with its driver.
"""

import importlib
import pkgutil
from pathlib import Path

def discover_and_register_drivers():
    """Discover and register all available drivers."""
    drivers_dir = Path(__file__).parent

    for _, module_name, is_pkg in pkgutil.iter_modules([str(drivers_dir)]):
        if is_pkg:  # Each driver is a package
            try:
                importlib.import_module(f".{module_name}", package=__name__)
            except ImportError as e:
                # Log but don't fail - driver may have missing dependencies
                logger.warning(f"Failed to load driver '{module_name}': {e}")

# Auto-discover on import
discover_and_register_drivers()
```

---

## 4. Example Driver Implementation

### 4.1 VASP Driver Bundle

```python
# src/quantumvitas/drivers/vasp/__init__.py

from .driver import VASPDriver
from quantumvitas.core.driver_registry import DriverRegistry

# Register driver at import time
DriverRegistry.register(VASPDriver())
```

```python
# src/quantumvitas/drivers/vasp/driver.py

from quantumvitas.core.driver_protocol import (
    EngineDriver,
    EngineCapabilities,
    WorkdirPolicy,
    PreflightRequirement,
    StepTypeSpec,
)
from .recipe import VASPRecipe
from .handler import vasp_step_handler
from .resolver import VASPExecutableResolver
from .done_policy import VASPDonePolicy


class VASPDriver:
    """VASP engine driver implementation."""

    # =========================================================================
    # Identity
    # =========================================================================

    @property
    def engine_family(self) -> str:
        return "vasp"

    @property
    def engine_display_name(self) -> str:
        return "VASP"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # =========================================================================
    # Registration
    # =========================================================================

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(
                id="vasp_scf",
                machine_type="vasp_scf",
                engine="vasp",
                executable="vasp_std",
                description="VASP single-point SCF calculation",
            ),
            StepTypeSpec(
                id="vasp_relax",
                machine_type="vasp_relax",
                engine="vasp",
                executable="vasp_std",
                description="VASP geometry relaxation",
            ),
            StepTypeSpec(
                id="vasp_md",
                machine_type="vasp_md",
                engine="vasp",
                executable="vasp_std",
                description="VASP molecular dynamics",
                supports_incremental_skip=False,
            ),
            StepTypeSpec(
                id="vasp_bands",
                machine_type="vasp_bands",
                engine="vasp",
                executable="vasp_std",
                description="VASP band structure calculation",
            ),
            StepTypeSpec(
                id="vasp_dos",
                machine_type="vasp_dos",
                engine="vasp",
                executable="vasp_std",
                description="VASP density of states calculation",
            ),
        ]

    def get_recipe_class(self) -> type:
        return VASPRecipe

    def get_handler(self):
        return vasp_step_handler

    def get_materialization_map(self) -> dict[str, str]:
        return {
            "GEN_SCF": "vasp_scf",
            "GEN_RELAX": "vasp_relax",
            "GEN_MD": "vasp_md",
        }

    # =========================================================================
    # Capabilities
    # =========================================================================

    def get_capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            supports_scf=True,
            supports_relax=True,
            supports_md=True,
            supports_bands=True,
            supports_dos=True,
            supports_phonon=True,
            supports_restart=False,  # VASP uses CHGCAR/WAVECAR instead
            supports_charge_continuation=True,
            supports_wfn_continuation=True,
            supports_mpi=True,
            supports_openmp=False,  # VASP uses MPI, not OpenMP
            supports_gpu=True,  # VASP 6+ with GPU support
            supports_periodic=True,
            supports_molecular=True,  # With large box
            supports_surface=True,
            supports_spin_polarized=True,
            supports_soc=True,
            supports_dft_plus_u=True,
            supports_hybrid_functionals=True,
            supports_vdw_corrections=True,
        )

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        requirements = []
        params = step.parameters

        # CHGCAR continuation
        if params.get("icharg") in (1, 11):
            requirements.append(PreflightRequirement(
                artifact_type="chgcar",
                pattern="CHGCAR",
                source_step="predecessor",
                required=True,
                message="CHGCAR required for ICHARG={icharg} but not found in {source_dir}",
            ))

        # WAVECAR continuation
        if params.get("istart", 0) > 0:
            requirements.append(PreflightRequirement(
                artifact_type="wavecar",
                pattern="WAVECAR",
                source_step="predecessor",
                required=True,
                message="WAVECAR required for ISTART={istart} but not found in {source_dir}",
            ))

        return requirements

    # =========================================================================
    # Artifacts
    # =========================================================================

    def get_artifact_patterns(self) -> dict[str, str]:
        return {
            "chgcar": "CHGCAR",
            "wavecar": "WAVECAR",
            "outcar": "OUTCAR",
            "contcar": "CONTCAR",
            "trajectory": "XDATCAR",
            "energy": "OSZICAR",
        }

    def find_latest_artifact(self, workdir, artifact_type) -> Path | None:
        pattern = self.get_artifact_patterns().get(artifact_type)
        if not pattern:
            return None

        # VASP has fixed filenames, no mtime selection needed
        candidate = workdir / pattern
        return candidate if candidate.exists() else None

    # =========================================================================
    # Workdir Policy
    # =========================================================================

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.CLEANUP  # VASP cleans workdir each step

    # =========================================================================
    # Done/Skip Policy
    # =========================================================================

    def get_done_policy_class(self):
        return VASPDonePolicy

    def supports_incremental_skip(self, step_type: str) -> bool:
        # MD steps don't support incremental skip
        return step_type != "vasp_md"

    # =========================================================================
    # Executable Discovery
    # =========================================================================

    def get_executable_resolver(self):
        return VASPExecutableResolver()
```

---

## 5. Kernel Integration Points

### 5.1 Handler Dispatch (Refactored)

```python
# src/quantumvitas/execution/handlers.py (refactored)

from quantumvitas.core.driver_registry import DriverRegistry

def get_handler_for_step(step: Step):
    """Get handler for step using driver registry."""
    driver = DriverRegistry.get_driver_for_step_type(step.step_type)
    return driver.get_handler()
```

### 5.2 Recipe Selection (Refactored)

```python
# src/quantumvitas/execution/recipes.py (refactored)

from quantumvitas.core.driver_registry import DriverRegistry

def get_recipe_class(engine_family: str) -> type:
    """Get recipe class using driver registry."""
    driver = DriverRegistry.get_driver(engine_family)
    return driver.get_recipe_class()
```

### 5.3 Engine Detection (Refactored)

```python
# src/quantumvitas/core/calc_identity.py (refactored)

from quantumvitas.core.driver_registry import DriverRegistry

def determine_engine_family(machine_type: str) -> str:
    """Determine engine family from step type. No fallbacks."""
    driver = DriverRegistry.get_driver_for_step_type(machine_type)
    return driver.engine_family
```

---

## 6. API Versioning Strategy

### 6.1 Version Format

```
MAJOR.MINOR.PATCH

Example: 1.2.3
- MAJOR (1): Breaking protocol changes
- MINOR (2): New optional methods added
- PATCH (3): Bug fixes, documentation
```

### 6.2 Compatibility Rules

| Change Type | Version Bump | Backward Compatible |
|-------------|--------------|---------------------|
| Add optional method | MINOR | Yes |
| Add required method | MAJOR | No |
| Remove method | MAJOR | No |
| Change method signature | MAJOR | No |
| Add capability flag | MINOR | Yes |
| Bug fix | PATCH | Yes |

### 6.3 Deprecation Policy

1. **Deprecation notice**: Log warning for one MINOR version
2. **Removal**: Remove in next MAJOR version
3. **Migration guide**: Document in release notes

---

## 7. Directory Structure

```
src/quantumvitas/
├── core/
│   ├── driver_protocol.py      # EngineDriver Protocol
│   ├── driver_registry.py      # DriverRegistry class
│   └── driver_exceptions.py    # Driver-specific exceptions
│
├── drivers/
│   ├── __init__.py             # Auto-discovery
│   │
│   ├── qe/
│   │   ├── __init__.py         # Register QEDriver
│   │   ├── driver.py           # QEDriver implementation
│   │   ├── recipe.py           # QERecipe
│   │   ├── handler.py          # qe_step_handler
│   │   ├── writer.py           # Input file generation
│   │   ├── parser.py           # Output parsing
│   │   └── resolver.py         # Executable discovery
│   │
│   ├── vasp/
│   │   ├── __init__.py
│   │   ├── driver.py
│   │   ├── recipe.py
│   │   ├── handler.py
│   │   ├── staging.py          # VASP-specific staging
│   │   ├── reference.py        # CHGCAR/WAVECAR resolution
│   │   └── resolver.py
│   │
│   ├── orca/
│   │   └── ...
│   │
│   ├── pyscf/
│   │   └── ...
│   │
│   ├── lammps/
│   │   └── ...
│   │
│   ├── cp2k/
│   │   └── ...
│   │
│   └── w90/
│       └── ...
│
└── execution/
    ├── handlers.py             # Thin dispatcher (uses registry)
    └── recipes.py              # Thin dispatcher (uses registry)
```

---

## 8. Success Criteria

### 8.1 Functional Requirements

- [ ] All 7 engines migrated to driver model
- [ ] No engine-specific code in kernel
- [ ] Explicit error on unknown step types (no fallbacks)
- [ ] All existing tests pass
- [ ] New driver can be added without modifying kernel

### 8.2 Quality Requirements

- [ ] Each driver is self-contained package
- [ ] API version validated at registration
- [ ] Comprehensive documentation for driver authors
- [ ] Example driver template provided

### 8.3 Performance Requirements

- [ ] Registration adds < 100ms startup time
- [ ] Driver lookup is O(1)
- [ ] No runtime reflection/introspection
