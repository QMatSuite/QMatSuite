"""Gaussian engine driver.

Implements the 7-item MUST interface for Gaussian quantum chemistry engine.
Gaussian is an external binary engine similar to ORCA that handles HF, DFT,
MP2, CCSD, TDDFT, geometry optimization, and frequency calculations.
"""

from __future__ import annotations

from quantumvitas.core.analysis.capability import AnalysisCapability
from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    ErrorClass,
    StepTypeSpec,
    WorkdirPolicy,
)


class GaussianDriver(BaseEngineDriver):
    """Driver for the Gaussian quantum chemistry engine.

    Recipe archetype: Strong-chain with ISOLATED workdir.
    Each step gets its own working directory. Checkpoint files (.chk)
    can be used for restart if needed.
    """

    PREFIX: str = "gaussian"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "hf", "relax", "freq", "mp2", "td"
    })
    ENGINE_ROLE: str = "base"
    COMPANION_ENGINES: frozenset = frozenset()
    ANALYSIS_CAPABILITIES = [
        AnalysisCapability(
            object_type="trajectory",
            gen_step_sequence=["relax"],
            evidence_files=["*.log"],
        ),
    ]

    # ── MUST: Properties ──────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "gaussian"

    @property
    def display_name(self) -> str:
        return "Gaussian"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ── MUST: Methods ─────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(
                step_type_spec="gaussian_scf",
                engine="gaussian",
                executable="g09",
                description="Gaussian DFT/HF single-point calculation",
                category="calculation",
                supports_restart=True,
                mpi_aware=False,
            ),
            StepTypeSpec(
                step_type_spec="gaussian_hf",
                engine="gaussian",
                executable="g09",
                description="Gaussian Hartree-Fock calculation",
                category="calculation",
                supports_restart=True,
                mpi_aware=False,
            ),
            StepTypeSpec(
                step_type_spec="gaussian_relax",
                engine="gaussian",
                executable="g09",
                description="Gaussian geometry optimization",
                category="calculation",
                supports_restart=True,
                mpi_aware=False,
            ),
            StepTypeSpec(
                step_type_spec="gaussian_freq",
                engine="gaussian",
                executable="g09",
                description="Gaussian frequency/vibrational analysis",
                category="calculation",
                supports_restart=False,
                mpi_aware=False,
            ),
            StepTypeSpec(
                step_type_spec="gaussian_mp2",
                engine="gaussian",
                executable="g09",
                description="Gaussian MP2 correlation energy",
                category="calculation",
                supports_restart=True,
                mpi_aware=False,
            ),
            StepTypeSpec(
                step_type_spec="gaussian_td",
                engine="gaussian",
                executable="g09",
                description="Gaussian TDDFT excited states",
                category="calculation",
                supports_restart=False,
                mpi_aware=False,
            ),
        ]

    def get_handler(self):
        from .handler import gaussian_step_handler
        return gaussian_step_handler

    def get_recipe_class(self):
        from .recipe import GaussianRecipe
        return GaussianRecipe

    def get_input_spec(self, **context):
        """Return Gaussian input format specification."""
        from .inputspec import get_gaussian_input_spec
        return get_gaussian_input_spec(**context)

    # ── SHOULD: Overrides ─────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        return {"scf", "hf", "relax", "freq", "mp2", "td", "molecular"}

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        # MP2 and TD are always recomputed with the chain
        if step_type_spec in ("gaussian_mp2", "gaussian_td"):
            return False
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        lower = stderr.lower()
        if "convergence" in lower or "not converged" in lower:
            return ErrorClass.CONVERGENCE
        if "out-of-memory" in lower or "memory" in lower:
            return ErrorClass.MEMORY
        if "file not found" in lower or "cannot open" in lower:
            return ErrorClass.MISSING_FILE
        if "error termination" in lower:
            return ErrorClass.UNKNOWN
        return ErrorClass.UNKNOWN

    def get_artifact_patterns(self) -> dict[str, str]:
        return {
            "input": "*.gjf",
            "output": "*.log",
            "checkpoint": "*.chk",
            "formatted_checkpoint": "*.fchk",
        }
