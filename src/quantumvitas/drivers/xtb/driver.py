"""xTB engine driver.

Implements the 7-item MUST interface for the xTB semi-empirical engine.
xTB is a single-binary, OpenMP-only engine that operates on XYZ files
with CLI flags. Primary use case: fast geometry optimization (relax).
"""

from __future__ import annotations

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    ErrorClass,
    StepTypeSpec,
    WorkdirPolicy,
)


class XTBDriver(BaseEngineDriver):
    """Driver for the xTB semi-empirical engine.

    Recipe archetype: Directory-state with ISOLATED workdir.
    Each step gets its own working directory. No restart staging needed
    (xTB calculations are fast enough to recompute).
    """

    PREFIX: str = "xtb"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({"relax"})

    # ── MUST: Properties ──────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "xtb"

    @property
    def display_name(self) -> str:
        return "xTB"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ── MUST: Methods ─────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(
                step_type_spec="xtb_relax",
                engine="xtb",
                executable="xtb",
                description="xTB geometry optimization (GFN2-xTB)",
                category="calculation",
                supports_restart=False,
                mpi_aware=False,
            ),
        ]

    def get_handler(self):
        from .handler import xtb_step_handler
        return xtb_step_handler

    def get_recipe_class(self):
        from .recipe import XTBRecipe
        return XTBRecipe

    def get_input_spec(self, **context):
        """Return xTB input format specification."""
        from .inputspec import get_xtb_input_spec
        return get_xtb_input_spec(**context)

    # ── SHOULD: Overrides ─────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        return {"relax", "molecular"}

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        lower = stderr.lower()
        if "convergence" in lower or "not converged" in lower:
            return ErrorClass.CONVERGENCE
        if "cannot open" in lower or "not found" in lower:
            return ErrorClass.MISSING_FILE
        if "memory" in lower or "allocation" in lower:
            return ErrorClass.MEMORY
        return ErrorClass.UNKNOWN

    def get_artifact_patterns(self) -> dict[str, str]:
        return {
            "optimized_geometry": "xtbopt.xyz",
            "trajectory": "xtbopt.log",
            "log": "xtb.out",
            "charges": "charges",
            "bond_orders": "wbo",
            "success_marker": ".xtboptok",
        }
