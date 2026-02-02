"""CP2K engine driver.

This driver handles all CP2K calculations including:
- SCF calculations (DFT, HF, hybrid)
- Geometry and cell optimization
- Molecular dynamics
- Band structure and DOS calculations
"""

from pathlib import Path

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    PreflightRequirement,
    ErrorClass,
)


class CP2KDriver(BaseEngineDriver):
    """CP2K driver bundle implementing the EngineDriver protocol."""

    PREFIX: str = "cp2k"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "relax", "md", "bandspw", "dos"
    })

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "cp2k"

    @property
    def display_name(self) -> str:
        return "CP2K"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return CP2K step type specifications."""
        return [
            StepTypeSpec(
                step_type_spec="cp2k_scf",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K SCF calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="cp2k_relax",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K geometry relaxation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="cp2k_geo_opt",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K geometry optimization",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="cp2k_cell_opt",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K cell optimization",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="cp2k_md",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K molecular dynamics",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                step_type_spec="cp2k_bandspw",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K band structure calculation (eigenstates along k-path)",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="cp2k_dos",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K density of states",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="cp2k_vibrational",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K vibrational analysis",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return CP2K step handler."""
        from .handler import cp2k_step_handler
        return cp2k_step_handler

    def get_recipe_class(self):
        """Return CP2K recipe class."""
        from .recipe import CP2KRecipe
        return CP2KRecipe


    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where CP2K differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """CP2K uses isolated workdir."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """CP2K capabilities."""
        return {
            "scf", "relax", "md", "bands", "dos",
            "geo_opt", "cell_opt", "vibrational",
            "periodic", "molecular", "mpi",
            "restart", "wfn_continuation",
        }

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        """MD steps should not be skipped."""
        if step_type_spec == "cp2k_md":
            return False
        return True

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        """CP2K preflight requirements (restart, basis sets)."""
        requirements = []

        step_config = getattr(step, "config", {}) or {}

        # Check for wavefunction restart
        if step_config.get("restart_wfn", False):
            requirements.append(PreflightRequirement(
                artifact_type="RESTART.wfn",
                source_step=step_config.get("restart_source"),
                required=True,
                description="CP2K wavefunction restart file",
            ))

        return requirements

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify CP2K errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "scf run not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "out of memory" in stderr_lower:
            return ErrorClass.MEMORY
        if "timeout" in stderr_lower or exit_code == 124:
            return ErrorClass.TIMEOUT
        if "file not found" in stderr_lower or "cannot open" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "input error" in stderr_lower or "unknown keyword" in stderr_lower:
            return ErrorClass.INPUT_ERROR
        if "cp2k" in stderr_lower and "not found" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """CP2K artifact patterns for discovery."""
        return {
            "restart_wfn": "*RESTART.wfn*",
            "output": "*.out",
            "trajectory": "*-pos-*.xyz",
            "forces": "*-frc-*.xyz",
            "pdos": "*-k*.pdos",
            "cube": "*.cube",
        }

    def find_latest_artifact(self, workdir: Path, artifact_type: str) -> Path | None:
        """Find latest CP2K artifact."""
        pattern = self.get_artifact_patterns().get(artifact_type)
        if not pattern:
            return None

        matches = sorted(
            workdir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return matches[0] if matches else None

