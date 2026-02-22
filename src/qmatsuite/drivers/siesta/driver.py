"""Siesta engine driver.

Implements the 7-item MUST interface for the Siesta DFT engine.
Siesta uses numerical atomic orbitals (NAO) as basis sets and
norm-conserving pseudopotentials in PSF/PSML format.
"""

from __future__ import annotations

from qmatsuite.core.analysis.capability import AnalysisCapability
from qmatsuite.core.driver_protocol import (
    BaseEngineDriver,
    ErrorClass,
    StepTypeSpec,
    WorkdirPolicy,
)


class SiestaDriver(BaseEngineDriver):
    """Driver for the Siesta DFT engine.

    Recipe archetype: Directory-state with ISOLATED workdir.
    Each step gets its own working directory. Restart via .DM file staging.
    """

    PREFIX: str = "siesta"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "relax", "md", "bands", "dos",
    })
    ENGINE_ROLE: str = "base"
    COMPANION_ENGINES: frozenset = frozenset()
    ANALYSIS_CAPABILITIES = [
        AnalysisCapability(
            object_type="bands",
            gen_step_sequence=["bands"],
            evidence_files=["*.EIG"],
        ),
        AnalysisCapability(
            object_type="dos",
            gen_step_sequence=["dos"],
            evidence_files=["*.DOS"],
        ),
        AnalysisCapability(
            object_type="convergence",
            gen_step_sequence=["scf"],
            evidence_files=["*.out"],
        ),
        AnalysisCapability(
            object_type="convergence",
            gen_step_sequence=["relax"],
            evidence_files=["*.out"],
        ),
        AnalysisCapability(
            object_type="trajectory",
            gen_step_sequence=["relax"],
            evidence_files=["*.ANI", "*.MD_CAR"],
        ),
        AnalysisCapability(
            object_type="trajectory",
            gen_step_sequence=["md"],
            evidence_files=["*.ANI", "*.MD_CAR"],
        ),
        AnalysisCapability(
            object_type="field3d",
            gen_step_sequence=["scf"],
            evidence_files=["*.cube"],
        ),
    ]

    # ── MUST: Properties ──────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "siesta"

    @property
    def display_name(self) -> str:
        return "Siesta"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ── MUST: Methods ─────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(
                step_type_spec="siesta_scf",
                engine="siesta",
                executable="siesta",
                description="Siesta SCF energy calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="siesta_relax",
                engine="siesta",
                executable="siesta",
                description="Siesta geometry optimization (CG/Broyden/FIRE)",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="siesta_md",
                engine="siesta",
                executable="siesta",
                description="Siesta molecular dynamics",
                supports_restart=True,
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="siesta_bands",
                engine="siesta",
                executable="siesta",
                description="Siesta band structure (via BandLines in SCF)",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="siesta_dos",
                engine="siesta",
                executable="siesta",
                description="Siesta density of states",
                mpi_aware=True,
            ),
        ]

    def get_handler(self):
        from .handler import siesta_step_handler
        return siesta_step_handler

    def get_recipe_class(self):
        from .recipe import SiestaRecipe
        return SiestaRecipe

    def get_input_spec(self, **context):
        """Return Siesta input format specification."""
        from .inputspec import get_siesta_input_spec
        return get_siesta_input_spec(**context)

    # ── SHOULD: Overrides ─────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        return {
            "scf", "relax", "md", "bands", "dos",
            "periodic", "molecular", "mpi",
        }

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        return step_type_spec != "siesta_md"

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        lower = stderr.lower()
        if "scf_not_converged" in lower or "convergence" in lower:
            return ErrorClass.CONVERGENCE
        if "pseudo_read: error" in lower or "pseudopotential" in lower:
            return ErrorClass.MISSING_FILE
        if "memory" in lower or "allocation" in lower:
            return ErrorClass.MEMORY
        return ErrorClass.UNKNOWN

    def get_artifact_patterns(self) -> dict[str, str]:
        return {
            "restart": "*.DM",
            "log": "*.out",
            "forces": "*.FA",
            "structure": "*.STRUCT_OUT",
            "eigenvalues": "*.EIG",
            "normal_exit": "0_NORMAL_EXIT",
        }
