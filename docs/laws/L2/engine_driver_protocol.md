# Engine Driver Protocol

**Version**: 1.0
**Status**: SPECIFICATION

---

## 1. Overview

This document specifies the `EngineDriver` interface that all engine integrations must implement. The interface is organized into three tiers to balance completeness with ease of implementation.

---

## 2. Interface Tiers

| Tier | Purpose | Required For |
|------|---------|--------------|
| **MUST** | Minimal interface for routing and execution | All drivers |
| **SHOULD** | Preflight, UX, diagnostics | Production drivers |
| **PLUGIN** | Advanced features, optimizations | Feature-rich drivers |

A minimal driver implements only MUST methods. Sensible defaults are provided for SHOULD/PLUGIN methods.

---

## 3. MUST Interface (Required)

Every driver MUST implement these methods. Without them, the driver cannot be registered or used.

```python
from typing import Callable, Any
from dataclasses import dataclass

class EngineDriver:
    """Minimal required interface for engine drivers."""

    # ─────────────────────────────────────────────────────────────
    # MUST: Identity (3 properties)
    # ─────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        """
        Unique identifier for this engine.

        Examples: "qe", "vasp", "orca", "pyscf", "lammps", "cp2k"

        MUST be lowercase alphanumeric + underscore.
        MUST be unique across all registered drivers.
        """
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name for UI/logs. E.g., 'Quantum ESPRESSO'."""
        ...

    @property
    def driver_api_version(self) -> str:
        """
        Semver string: "MAJOR.MINOR.PATCH"

        Current kernel requires MAJOR=1.
        """
        ...

    # ─────────────────────────────────────────────────────────────
    # MUST: Registration (3 methods)
    # ─────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list["StepTypeSpec"]:
        """
        Return all step types this driver handles.

        Each StepTypeSpec MUST have unique `id`.
        These are registered in STEP_TYPE_REGISTRY.
        """
        ...

    def get_handler(self) -> Callable[["Job", "Context"], "JobResult"]:
        """
        Return the step handler function.

        Handler signature: (job: Job, ctx: Context) -> JobResult
        Handler is invoked by kernel to execute a step.
        """
        ...

    def get_recipe_class(self) -> type["BaseRecipe"]:
        """
        Return the recipe class for input staging.

        Recipe is instantiated by kernel before handler invocation.
        """
        ...

    # ─────────────────────────────────────────────────────────────
    # MUST: Materialization (1 method)
    # ─────────────────────────────────────────────────────────────

    def get_materialization_map(self) -> dict[str, str]:
        """
        Return mapping: generalized_step_type → machine_step_type

        Keys: "GEN_SCF", "GEN_RELAX", "GEN_MD", etc.
        Values: Machine step types declared in get_step_type_specs()

        Return empty dict if engine doesn't support generalized steps.
        """
        ...
```

### 3.1 StepTypeSpec (Data Structure)

```python
@dataclass(frozen=True)
class StepTypeSpec:
    """Specification for a machine step type."""

    id: str
    """Unique identifier. E.g., 'vasp_scf'. MUST match engine_family prefix."""

    engine: str
    """Engine family. MUST match driver.engine_family."""

    executable: str
    """Executable name. E.g., 'vasp_std', 'pw.x'."""

    description: str = ""
    """Human-readable description for UI."""
```

### 3.2 Minimal Example

```python
class MinimalDriver:
    """Smallest possible valid driver."""

    @property
    def engine_family(self) -> str:
        return "minimal"

    @property
    def display_name(self) -> str:
        return "Minimal Engine"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(
                id="minimal_calc",
                engine="minimal",
                executable="minimal.exe",
            )
        ]

    def get_handler(self):
        def handler(job, ctx):
            # Execute minimal_calc
            return JobResult(success=True)
        return handler

    def get_recipe_class(self):
        return MinimalRecipe

    def get_materialization_map(self) -> dict[str, str]:
        return {"GEN_SCF": "minimal_calc"}
```

---

## 4. SHOULD Interface (Recommended)

These methods improve UX, diagnostics, and robustness. Sensible defaults are provided.

```python
class EngineDriver:
    # ... MUST methods above ...

    # ─────────────────────────────────────────────────────────────
    # SHOULD: Workdir Policy
    # ─────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> "WorkdirPolicy":
        """
        Declare workdir handling.

        DEFAULT: WorkdirPolicy.ISOLATED (per-step workdir, no cleanup)

        Options:
        - ISOLATED: Each step gets raw/<step_ulid>/, no cleanup
        - CLEANUP: rm -rf workdir before each step (VASP pattern)
        - SHARED: Shared outdir with prefix namespacing (QE pattern)
        """
        return WorkdirPolicy.ISOLATED  # default

    # ─────────────────────────────────────────────────────────────
    # SHOULD: Capabilities
    # ─────────────────────────────────────────────────────────────

    def get_capabilities(self) -> set[str]:
        """
        Declare engine capabilities as string tags.

        DEFAULT: empty set (no declared capabilities)

        Standard tags:
        - "scf", "relax", "md", "bands", "dos", "phonon"
        - "periodic", "molecular"
        - "mpi", "openmp", "gpu"
        - "restart", "continuation"

        Used for: UI hints, validation, feature gating.
        Custom tags allowed (engine-prefixed recommended).
        """
        return set()  # default

    # ─────────────────────────────────────────────────────────────
    # SHOULD: Incremental Skip
    # ─────────────────────────────────────────────────────────────

    def supports_incremental_skip(self, step_type: str) -> bool:
        """
        Whether a step type can be skipped if already done.

        DEFAULT: True (most steps can be skipped)

        Return False for:
        - MD steps (always re-run when targeted)
        - Steps with external side effects
        """
        return True  # default

    # ─────────────────────────────────────────────────────────────
    # SHOULD: Preflight
    # ─────────────────────────────────────────────────────────────

    def get_preflight_requirements(
        self, step: "Step"
    ) -> list["PreflightRequirement"]:
        """
        Declare artifacts required before step execution.

        DEFAULT: empty list (no preflight checks)

        Kernel invokes preflight checker before handler.
        Missing required artifacts raise PreflightError.
        """
        return []  # default

    # ─────────────────────────────────────────────────────────────
    # SHOULD: Error Classification
    # ─────────────────────────────────────────────────────────────

    def classify_error(self, stderr: str, exit_code: int) -> "ErrorClass":
        """
        Classify engine error for user-friendly messaging.

        DEFAULT: ErrorClass.UNKNOWN

        Return values:
        - ErrorClass.CONVERGENCE: SCF/optimization didn't converge
        - ErrorClass.MEMORY: Out of memory
        - ErrorClass.INPUT: Bad input parameters
        - ErrorClass.LICENSE: License issue
        - ErrorClass.UNKNOWN: Unclassified
        """
        return ErrorClass.UNKNOWN  # default
```

### 4.1 WorkdirPolicy Enum

```python
from enum import Enum

class WorkdirPolicy(Enum):
    ISOLATED = "isolated"    # Per-step workdir, no cleanup (default)
    CLEANUP = "cleanup"      # rm -rf before each step
    SHARED = "shared"        # Shared outdir with prefix namespacing
```

### 4.2 PreflightRequirement

```python
@dataclass(frozen=True)
class PreflightRequirement:
    artifact_type: str    # "restart", "wfn", "chgcar", etc.
    pattern: str          # Glob pattern: "CHGCAR", "*.wfn"
    source: str           # "predecessor" or step_ulid
    required: bool        # Hard error if missing?
    message: str          # Error template: "CHGCAR not found in {source_dir}"
```

---

## 5. PLUGIN Interface (Optional Extensions)

These methods enable advanced features. Drivers MAY implement them for richer functionality.

```python
class EngineDriver:
    # ... MUST and SHOULD methods above ...

    # ─────────────────────────────────────────────────────────────
    # PLUGIN: Artifact Discovery
    # ─────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """
        Declare glob patterns for artifact types.

        DEFAULT: empty dict

        Example:
            {"trajectory": "*.xyz", "restart": "*.restart", "wfn": "*.wfn"}
        """
        return {}  # default

    def find_latest_artifact(
        self, workdir: "Path", artifact_type: str
    ) -> "Path | None":
        """
        Find latest artifact by type, using mtime selection.

        DEFAULT: None (artifact discovery not supported)

        Called by kernel when staging from predecessor step.
        """
        return None  # default

    # ─────────────────────────────────────────────────────────────
    # PLUGIN: Resume/Continuation
    # ─────────────────────────────────────────────────────────────

    def get_resume_artifacts(self, step: "Step") -> list[str]:
        """
        Return artifact types needed to resume a failed step.

        DEFAULT: empty list (resume not supported)

        Example for LAMMPS: ["restart"]
        Example for CP2K: ["wfn", "restart"]
        """
        return []  # default

    def prepare_continuation(
        self, failed_step: "Step", artifacts: dict[str, "Path"]
    ) -> dict[str, Any]:
        """
        Prepare parameters for continuing a failed step.

        DEFAULT: empty dict (continuation not customized)

        Returns parameter overrides for the continuation run.
        """
        return {}  # default

    # ─────────────────────────────────────────────────────────────
    # PLUGIN: Executable Resolution
    # ─────────────────────────────────────────────────────────────

    def resolve_executable(self, step_type: str) -> "Path | None":
        """
        Find the executable for a step type.

        DEFAULT: None (use PATH lookup)

        Called before execution to locate engine binary.
        May check environment variables, config files, etc.
        """
        return None  # default

    # ─────────────────────────────────────────────────────────────
    # PLUGIN: Output Parsing
    # ─────────────────────────────────────────────────────────────

    def parse_output(
        self, workdir: "Path", step_type: str
    ) -> dict[str, Any]:
        """
        Parse engine output into structured data.

        DEFAULT: empty dict (no parsing)

        Returns dict with extracted values:
            {"energy": -123.45, "forces": [...], "converged": True}
        """
        return {}  # default
```

---

## 6. Defaults Summary

| Method | Default | Behavior |
|--------|---------|----------|
| `get_workdir_policy()` | `ISOLATED` | Per-step workdir, no cleanup |
| `get_capabilities()` | `set()` | No capabilities declared |
| `supports_incremental_skip()` | `True` | All steps skippable |
| `get_preflight_requirements()` | `[]` | No preflight checks |
| `classify_error()` | `UNKNOWN` | No error classification |
| `get_artifact_patterns()` | `{}` | No artifact discovery |
| `find_latest_artifact()` | `None` | Artifact lookup unsupported |
| `get_resume_artifacts()` | `[]` | Resume not supported |
| `prepare_continuation()` | `{}` | No continuation customization |
| `resolve_executable()` | `None` | Use PATH lookup |
| `parse_output()` | `{}` | No output parsing |

---

## 7. Implementation Pattern

### 7.1 Base Class (Optional)

Drivers MAY inherit from a base class that provides defaults:

```python
class BaseEngineDriver:
    """Base class with default implementations for SHOULD/PLUGIN methods."""

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        return set()

    def supports_incremental_skip(self, step_type: str) -> bool:
        return True

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        return []

    # ... other defaults ...
```

### 7.2 Full Example (VASP)

```python
class VASPDriver(BaseEngineDriver):
    """VASP engine driver with full SHOULD/PLUGIN implementation."""

    # ── MUST ──

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
        return [
            StepTypeSpec(id="vasp_scf", engine="vasp", executable="vasp_std"),
            StepTypeSpec(id="vasp_relax", engine="vasp", executable="vasp_std"),
            StepTypeSpec(id="vasp_md", engine="vasp", executable="vasp_std"),
        ]

    def get_handler(self):
        from .handler import vasp_handler
        return vasp_handler

    def get_recipe_class(self):
        from .recipe import VASPRecipe
        return VASPRecipe

    def get_materialization_map(self) -> dict[str, str]:
        return {
            "GEN_SCF": "vasp_scf",
            "GEN_RELAX": "vasp_relax",
            "GEN_MD": "vasp_md",
        }

    # ── SHOULD ──

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.CLEANUP  # VASP cleans each step

    def get_capabilities(self) -> set[str]:
        return {"scf", "relax", "md", "bands", "dos", "periodic", "mpi"}

    def supports_incremental_skip(self, step_type: str) -> bool:
        return step_type != "vasp_md"  # MD cannot be skipped

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        reqs = []
        if step.parameters.get("icharg") in (1, 11):
            reqs.append(PreflightRequirement(
                artifact_type="chgcar",
                pattern="CHGCAR",
                source="predecessor",
                required=True,
                message="CHGCAR required for ICHARG={value}",
            ))
        return reqs

    # ── PLUGIN ──

    def get_artifact_patterns(self) -> dict[str, str]:
        return {
            "chgcar": "CHGCAR",
            "wavecar": "WAVECAR",
            "trajectory": "XDATCAR",
        }

    def find_latest_artifact(self, workdir, artifact_type):
        pattern = self.get_artifact_patterns().get(artifact_type)
        if pattern:
            path = workdir / pattern
            return path if path.exists() else None
        return None
```

---

## 8. Validation Rules

### 8.1 Registration-Time Validation

When a driver is registered, the kernel validates:

| Check | Error if violated |
|-------|-------------------|
| `engine_family` is non-empty string | `InvalidDriverError` |
| `engine_family` is unique | `DuplicateEngineError` |
| `driver_api_version` is valid semver | `InvalidVersionError` |
| `driver_api_version` major matches kernel | `IncompatibleDriverError` |
| `get_step_type_specs()` returns non-empty list | `NoStepTypesError` |
| Each `StepTypeSpec.id` is unique | `DuplicateStepTypeError` |
| Each `StepTypeSpec.engine` matches driver | `EnginesMismatchError` |

### 8.2 Runtime Validation

During execution, the kernel may validate:

| Check | When | Error |
|-------|------|-------|
| Handler returns `JobResult` | After handler | `InvalidHandlerResultError` |
| Recipe is instantiable | Before staging | `RecipeInstantiationError` |
| Preflight requirements met | Before handler | `PreflightError` |

---

## 9. Versioning

### 9.1 API Version Semantics

```
MAJOR.MINOR.PATCH

1.0.0 → 1.1.0: Added optional PLUGIN method (backward compatible)
1.0.0 → 2.0.0: Changed MUST method signature (breaking)
```

### 9.2 Kernel Compatibility

| Kernel API | Compatible Driver API |
|------------|----------------------|
| 1.x | 1.x only |
| 2.x | 2.x only |

Drivers with mismatched MAJOR version will fail registration.

---

## 10. Import Cycle Mitigation

To avoid import cycles between kernel and drivers:

1. **Protocol is in kernel** (`core/driver_protocol.py`)
2. **Drivers import protocol** (not vice versa)
3. **Registry uses string paths** for lazy loading if needed
4. **Type hints use string annotations** (`"StepTypeSpec"` not `StepTypeSpec`)

```python
# Kernel: core/driver_protocol.py
class EngineDriver:
    def get_handler(self) -> Callable[["Job", "Context"], "JobResult"]:
        ...  # Forward references avoid imports

# Driver: drivers/vasp/__init__.py
from quantumvitas.core.driver_protocol import EngineDriver  # OK: driver imports kernel
from quantumvitas.core.driver_registry import DriverRegistry

class VASPDriver:
    ...

DriverRegistry.register(VASPDriver())
```
