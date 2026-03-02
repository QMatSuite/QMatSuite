"""MACE engine driver.

Implements the 7-item MUST interface for the MACE ML interatomic potential engine.
MACE is a Python-script engine that uses ASE Calculator objects for computing
energy/forces/stress at near-DFT accuracy with ML potentials.
"""

from __future__ import annotations

from qmatsuite.core.analysis.capability import AnalysisCapability
from qmatsuite.core.driver_protocol import (
    BaseEngineDriver,
    ErrorClass,
    StepTypeSpec,
    WorkdirPolicy,
)


class MACEDriver(BaseEngineDriver):
    """Driver for the MACE ML interatomic potential engine.

    Recipe archetype: Directory-state with ISOLATED workdir.
    Each step gets its own working directory. No restart staging needed
    (ML potential calculations are fast enough to recompute).
    """

    PREFIX: str = "mace"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({"scf", "relax", "md"})
    ENGINE_ROLE: str = "base"
    COMPANION_ENGINES: frozenset = frozenset()
    ANALYSIS_CAPABILITIES = [
        AnalysisCapability(
            object_type="convergence",
            gen_step_sequence=["scf"],
            evidence_files=["results.json"],
        ),
        AnalysisCapability(
            object_type="convergence",
            gen_step_sequence=["relax"],
            evidence_files=["results.json"],
        ),
        AnalysisCapability(
            object_type="trajectory",
            gen_step_sequence=["relax"],
            evidence_files=["trajectory.jsonl"],
        ),
        AnalysisCapability(
            object_type="trajectory",
            gen_step_sequence=["md"],
            evidence_files=["trajectory.jsonl"],
        ),
    ]

    # -- MUST: Properties -----------------------------------------------

    @property
    def engine_family(self) -> str:
        return "mace"

    @property
    def display_name(self) -> str:
        return "MACE"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # -- MUST: Methods --------------------------------------------------

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(
                step_type_spec="mace_scf",
                engine="mace",
                executable="python",
                description="MACE single-point energy/forces/stress calculation",
                category="calculation",
                supports_restart=False,
                mpi_aware=False,
            ),
            StepTypeSpec(
                step_type_spec="mace_relax",
                engine="mace",
                executable="python",
                description="MACE geometry optimization (ASE optimizer + ML potential)",
                category="calculation",
                supports_restart=False,
                mpi_aware=False,
            ),
            StepTypeSpec(
                step_type_spec="mace_md",
                engine="mace",
                executable="python",
                description="MACE molecular dynamics (ASE + ML potential)",
                category="calculation",
                supports_restart=False,
                mpi_aware=False,
            ),
        ]

    def get_handler(self):
        from .handler import mace_step_handler
        return mace_step_handler

    def get_recipe_class(self):
        from .recipe import MACERecipe
        return MACERecipe

    def get_input_spec(self, **context):
        """Return MACE input format specification."""
        from .inputspec import get_mace_input_spec
        return get_mace_input_spec(**context)

    # -- SHOULD: Overrides ----------------------------------------------

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        return {"scf", "relax", "md", "molecular", "periodic"}

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        lower = stderr.lower()
        if "cuda" in lower or "out of memory" in lower:
            return ErrorClass.MEMORY
        if "not found" in lower or "no module" in lower:
            return ErrorClass.MISSING_FILE
        if "model" in lower and ("load" in lower or "path" in lower):
            return ErrorClass.MISSING_FILE
        return ErrorClass.UNKNOWN

    def get_artifact_patterns(self) -> dict[str, str]:
        return {
            "results": "results.json",
            "trajectory": "trajectory.jsonl",
            "final_structure": "final_structure.json",
            "log": "opt.log",
        }
