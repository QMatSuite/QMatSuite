"""Wannier90 engine driver.

This driver handles Wannier90 calculations for constructing
maximally localized Wannier functions (MLWFs) from DFT output.

Note: The preprocessing step (wannierprep) is registered with
the W90 engine. This driver handles the main Wannier90 execution (wannier).
"""

from pathlib import Path
from typing import Any

from quantumvitas.core.analysis.capability import AnalysisCapability
from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    PreflightRequirement,
    ErrorClass,
)


class W90Driver(BaseEngineDriver):
    """Wannier90 driver bundle implementing the EngineDriver protocol.

    This driver handles:
    - wannier: Main Wannier90 execution using wannier90.x

    The wannierprep step is handled by the W90 engine driver.
    """

    PREFIX: str = "w90"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "wannierprep", "wannier"
    })
    ENGINE_ROLE: str = "postprocessing"
    COMPANION_ENGINES: frozenset = frozenset()
    ANALYSIS_CAPABILITIES = [
        AnalysisCapability(
            object_type="field3d",
            gen_step_sequence=["wannier"],
            evidence_files=["*_00001.xsf"],
        ),
    ]

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "w90"

    @property
    def display_name(self) -> str:
        return "Wannier90"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return Wannier90 step type specifications.

        Note: wannierprep is included in the W90 engine registry.
        """
        return [
            StepTypeSpec(
                step_type_spec="w90_wannierprep",
                engine="w90",
                executable="wannier90.x",
                description="Wannier90 preprocessing (generate .nnkp)",
                category="postprocess",
                mpi_aware=False,  # wannier90.x is typically serial
            ),
            StepTypeSpec(
                step_type_spec="w90_wannier",
                engine="w90",
                executable="wannier90.x",
                description="Wannier90 MLWF construction",
                category="postprocess",
                mpi_aware=False,  # wannier90.x is typically serial
            ),
        ]

    def get_handler(self):
        """Return Wannier90 step handler."""
        from .handler import wannier_handler
        return wannier_handler

    def get_recipe_class(self):
        """Return Wannier90 recipe class."""
        from .recipe import W90Recipe
        return W90Recipe

    def get_input_spec(self, **context):
        """Return Wannier90 input format specification."""
        from .inputspec import get_w90_input_spec
        return get_w90_input_spec(**context)

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where W90 differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """W90 uses isolated workdir."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """Wannier90 capabilities."""
        return {
            "wannier",
            "mlwf",  # Maximally localized Wannier functions
            "interpolation",  # Band interpolation
            "postprocess",
            "cross_engine",  # Requires DFT output
        }

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        """All W90 steps can be skipped if done."""
        return True

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        """Wannier90 preflight requirements.

        wannier requires output from wannierprep step.
        """
        if step.step_type_spec == "w90_wannier":
            return [
                PreflightRequirement(
                    artifact_type="w90_amn",
                    source_step=None,  # Auto-resolve from wannierprep
                    required=True,
                    description="Wannier90 .amn file from preprocessing",
                ),
                PreflightRequirement(
                    artifact_type="w90_mmn",
                    source_step=None,
                    required=True,
                    description="Wannier90 .mmn file from preprocessing",
                ),
                PreflightRequirement(
                    artifact_type="w90_eig",
                    source_step=None,
                    required=True,
                    description="Wannier90 .eig file from preprocessing",
                ),
            ]
        return []

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify Wannier90 errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "kmesh" in stderr_lower and "error" in stderr_lower:
            return ErrorClass.INPUT_ERROR
        if "disentanglement not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "wannierisation not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "file not found" in stderr_lower or ".amn" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "wannier90" in stderr_lower and "not found" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """Wannier90 artifact patterns for discovery."""
        return {
            "w90_amn": "*.amn",
            "w90_mmn": "*.mmn",
            "w90_eig": "*.eig",
            "w90_win": "*.win",
            "w90_wout": "*.wout",
            "w90_hr": "*_hr.dat",
            "w90_tb": "*_tb.dat",
            "w90_centres": "*_centres.xyz",
        }

    def find_latest_artifact(self, workdir: Path, artifact_type: str) -> Path | None:
        """Find Wannier90 artifact in workdir."""
        pattern = self.get_artifact_patterns().get(artifact_type)
        if not pattern:
            return None

        matches = list(workdir.glob(pattern))
        return matches[0] if matches else None

