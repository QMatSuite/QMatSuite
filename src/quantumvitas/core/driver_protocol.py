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
    from quantumvitas.execution.job_graph import Job
    from quantumvitas.execution.executor import JobResult


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


# StepContext is a placeholder type - actual implementation may vary
# For now, we use a dict[str, Any] to match existing handler signatures
StepContext = dict[str, Any]


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

    def get_handler(self) -> Callable[["Job", StepContext], "JobResult"]:
        """Return the step handler function.

        The handler is called for each step execution.
        Note: Actual handler signatures may vary; this is the protocol contract.
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

