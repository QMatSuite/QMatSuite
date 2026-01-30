"""LAMMPS engine driver.

This driver handles all LAMMPS molecular dynamics simulations including:
- Energy minimization
- NVE, NVT, NPT ensembles
- Structure relaxation
- Deformation studies

LAMMPS has special restart/checkpoint capabilities that are
handled by this driver.
"""

from pathlib import Path
from typing import Any

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    PreflightRequirement,
    ErrorClass,
)


class LAMMPSDriver(BaseEngineDriver):
    """LAMMPS driver bundle implementing the EngineDriver protocol."""

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "lammps"

    @property
    def display_name(self) -> str:
        return "LAMMPS"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return LAMMPS step type specifications."""
        return [
            StepTypeSpec(
                step_type_spec="lammps_minimize",
                engine="lammps",
                executable="lmp",
                description="LAMMPS energy minimization",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="lammps_md",
                engine="lammps",
                executable="lmp",
                description="LAMMPS molecular dynamics",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                step_type_spec="lammps_nve",
                engine="lammps",
                executable="lmp",
                description="LAMMPS NVE ensemble MD",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                step_type_spec="lammps_nvt",
                engine="lammps",
                executable="lmp",
                description="LAMMPS NVT ensemble MD",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                step_type_spec="lammps_npt",
                engine="lammps",
                executable="lmp",
                description="LAMMPS NPT ensemble MD",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                step_type_spec="lammps_relax",
                engine="lammps",
                executable="lmp",
                description="LAMMPS structure relaxation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="lammps_equilibrate",
                engine="lammps",
                executable="lmp",
                description="LAMMPS equilibration run",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                step_type_spec="lammps_deform",
                engine="lammps",
                executable="lmp",
                description="LAMMPS deformation study",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return LAMMPS step handler."""
        from .handler import lammps_step_handler
        return lammps_step_handler

    def get_recipe_class(self):
        """Return LAMMPS recipe class."""
        from .recipe import LAMMPSRecipe
        return LAMMPSRecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return LAMMPS GEN→SPEC mappings."""
        return {
            "GEN_MINIMIZE": "lammps_minimize",
            "GEN_MD": "lammps_md",
            "GEN_RELAX": "lammps_relax",
            "GEN_NVT": "lammps_nvt",
            "GEN_NPT": "lammps_npt",
        }

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where LAMMPS differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """LAMMPS uses isolated workdir with accumulation."""
        # LAMMPS accumulates trajectory files, restart files
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """LAMMPS capabilities."""
        return {
            "minimize", "md", "nve", "nvt", "npt",
            "relax", "deform",
            "periodic", "molecular", "mpi",
            "restart",  # Supports restart from checkpoint
            "trajectory",  # Produces trajectory files
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        """MD steps should not be skipped (continuation matters)."""
        md_steps = {"lammps_md", "lammps_nve", "lammps_nvt", "lammps_npt", "lammps_equilibrate"}
        if step_type in md_steps:
            return False
        return True

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        """LAMMPS preflight requirements (restart files, potentials)."""
        requirements = []

        step_config = getattr(step, "config", {}) or {}

        # Check for restart continuation
        if step_config.get("restart", False):
            requirements.append(PreflightRequirement(
                artifact_type="restart",
                source_step=step_config.get("restart_source"),
                required=True,
                description="LAMMPS restart file for continuation",
            ))

        # Check for potential files
        if step_config.get("potential_file"):
            requirements.append(PreflightRequirement(
                artifact_type="potential",
                source_step=None,  # Potential files are typically external
                required=True,
                description="Force field potential file",
            ))

        return requirements

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify LAMMPS errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "lost atoms" in stderr_lower:
            return ErrorClass.CONVERGENCE  # Simulation instability
        if "out of memory" in stderr_lower or "malloc" in stderr_lower:
            return ErrorClass.MEMORY
        if "timeout" in stderr_lower or exit_code == 124:
            return ErrorClass.TIMEOUT
        if "cannot open" in stderr_lower or "file not found" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "illegal" in stderr_lower or "unknown" in stderr_lower:
            return ErrorClass.INPUT_ERROR
        if "lmp" in stderr_lower and "not found" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """LAMMPS artifact patterns for discovery."""
        return {
            "restart": "*.restart*",
            "data": "*.data",
            "trajectory": "*.lammpstrj",
            "log": "log.lammps",
            "dump": "dump.*",
            "thermo": "thermo.dat",
        }

    def find_latest_artifact(self, workdir: Path, artifact_type: str) -> Path | None:
        """Find latest LAMMPS artifact (especially restart files)."""
        pattern = self.get_artifact_patterns().get(artifact_type)
        if not pattern:
            return None

        matches = sorted(
            workdir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return matches[0] if matches else None

