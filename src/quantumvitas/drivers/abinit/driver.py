"""ABINIT engine driver.

This driver handles ABINIT DFT calculations including:
- SCF ground state calculations
- Non-self-consistent (NSCF) calculations
- Structure relaxation (ionic + optional cell)
"""

from quantumvitas.core.analysis.capability import AnalysisCapability
from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    ErrorClass,
)


class AbinitDriver(BaseEngineDriver):
    """ABINIT driver bundle implementing the EngineDriver protocol."""

    PREFIX: str = "abinit"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "nscf", "relax", "md",
    })
    ENGINE_ROLE: str = "base"
    COMPANION_ENGINES: frozenset = frozenset()
    ANALYSIS_CAPABILITIES = [
        AnalysisCapability(
            object_type="bands",
            gen_step_sequence=["nscf"],
            evidence_files=["*_EIG"],
        ),
        AnalysisCapability(
            object_type="dos",
            gen_step_sequence=["nscf"],
            evidence_files=["*_DOS"],
        ),
        AnalysisCapability(
            object_type="convergence",
            gen_step_sequence=["scf"],
            evidence_files=["*.abo"],
        ),
        AnalysisCapability(
            object_type="convergence",
            gen_step_sequence=["relax"],
            evidence_files=["*.abo"],
        ),
        AnalysisCapability(
            object_type="trajectory",
            gen_step_sequence=["relax"],
            evidence_files=["*_HIST.nc"],
        ),
        AnalysisCapability(
            object_type="trajectory",
            gen_step_sequence=["md"],
            evidence_files=["*_HIST.nc"],
        ),
    ]

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "abinit"

    @property
    def display_name(self) -> str:
        return "ABINIT"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return ABINIT step type specifications."""
        return [
            StepTypeSpec(
                step_type_spec="abinit_scf",
                engine="abinit",
                executable="abinit",
                description="ABINIT ground state SCF calculation",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="abinit_nscf",
                engine="abinit",
                executable="abinit",
                description="ABINIT non-self-consistent calculation",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="abinit_relax",
                engine="abinit",
                executable="abinit",
                description="ABINIT structure relaxation",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="abinit_md",
                engine="abinit",
                executable="abinit",
                description="ABINIT molecular dynamics",
                category="calculation",
                supports_restart=False,
                mpi_aware=True,
            ),
        ]

    def get_handler(self):
        """Return ABINIT step handler."""
        from .handler import abinit_step_handler
        return abinit_step_handler

    def get_recipe_class(self):
        """Return ABINIT recipe class."""
        from .recipe import AbinitRecipe
        return AbinitRecipe

    def get_input_spec(self, **context):
        """Return ABINIT input format specification."""
        from .inputspec import get_abinit_input_spec
        return get_abinit_input_spec(**context)

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where ABINIT differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """ABINIT uses shared workdir (Directory-state archetype like QE)."""
        return WorkdirPolicy.SHARED

    def get_capabilities(self) -> set[str]:
        """ABINIT capabilities."""
        return {
            "scf", "nscf", "relax", "md",
            "periodic",
            "mpi",
            "plane_wave",
            "dfpt",  # Future phase
            "gw",    # Future phase
        }

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        """All current ABINIT steps support incremental skip."""
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify ABINIT errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "convergence" in stderr_lower or "not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "memory" in stderr_lower or "allocation" in stderr_lower:
            return ErrorClass.MEMORY
        if "no such file" in stderr_lower or "filenotfound" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "pseudopotential" in stderr_lower or "psp" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "input" in stderr_lower and "error" in stderr_lower:
            return ErrorClass.INPUT_ERROR
        if "syntax" in stderr_lower:
            return ErrorClass.INPUT_ERROR

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """ABINIT artifact patterns for discovery."""
        return {
            "output": "*.abo",
            "input": "*.abi",
            "density": "*o_DEN",
            "wavefunctions": "*o_WFK",
            "eigenvalues": "*o_EIG",
            "eigenvalues_nc": "*o_EIG.nc",
            "gsr": "*o_GSR.nc",
            "history": "*o_HIST.nc",
        }
