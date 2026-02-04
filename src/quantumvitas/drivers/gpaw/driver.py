"""GPAW engine driver.

This driver handles GPAW DFT calculations including:
- SCF ground state (PW, FD, LCAO modes)
- Non-self-consistent (fixed density) calculations
- Band structure
- Density of states
- Geometry relaxation via ASE optimizers
- Molecular dynamics via ASE
"""

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    ErrorClass,
)


class GPAWDriver(BaseEngineDriver):
    """GPAW driver bundle implementing the EngineDriver protocol."""

    PREFIX: str = "gpaw"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "nscf", "relax", "bandspw", "dos", "md",
    })

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "gpaw"

    @property
    def display_name(self) -> str:
        return "GPAW"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return GPAW step type specifications."""
        return [
            StepTypeSpec(
                step_type_spec="gpaw_scf",
                engine="gpaw",
                executable="python",
                description="GPAW ground state SCF calculation",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="gpaw_nscf",
                engine="gpaw",
                executable="python",
                description="GPAW non-self-consistent (fixed density) calculation",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="gpaw_relax",
                engine="gpaw",
                executable="python",
                description="GPAW geometry relaxation via ASE optimizer",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="gpaw_bandspw",
                engine="gpaw",
                executable="python",
                description="GPAW band structure (fixed density along k-path)",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="gpaw_dos",
                engine="gpaw",
                executable="python",
                description="GPAW density of states",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="gpaw_md",
                engine="gpaw",
                executable="python",
                description="GPAW molecular dynamics via ASE",
                category="calculation",
                mpi_aware=True,
            ),
        ]

    def get_handler(self):
        """Return GPAW step handler."""
        from .handler import gpaw_step_handler
        return gpaw_step_handler

    def get_recipe_class(self):
        """Return GPAW recipe class."""
        from .recipe import GPAWRecipe
        return GPAWRecipe

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where GPAW differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """GPAW uses shared workdir (chains via .gpw restart files)."""
        return WorkdirPolicy.SHARED

    def get_capabilities(self) -> set[str]:
        """GPAW capabilities."""
        return {
            "scf", "nscf", "relax", "bandspw", "dos", "md",
            "periodic", "molecular",
            "mpi",
            "python_native",
        }

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        """MD steps should not be skipped."""
        return step_type_spec != "gpaw_md"

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify GPAW errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "convergence" in stderr_lower or "not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "memory" in stderr_lower or "memoryerror" in stderr_lower:
            return ErrorClass.MEMORY
        if "no such file" in stderr_lower or "filenotfound" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "import" in stderr_lower and "gpaw" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND
        if "keyerror" in stderr_lower or "valueerror" in stderr_lower:
            return ErrorClass.INPUT_ERROR

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """GPAW artifact patterns for discovery."""
        return {
            "restart": "*.gpw",
            "log": "*.txt",
            "results": "results.json",
            "bandstructure": "bandstructure.json",
            "dos": "dos.json",
            "trajectory": "*.traj",
        }
