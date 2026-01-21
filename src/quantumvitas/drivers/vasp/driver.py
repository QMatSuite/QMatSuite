"""VASP engine driver.

This driver handles all VASP calculations including:
- SCF, relaxation, MD simulations
- Band structure, DOS calculations
- Phonon, elastic, dielectric calculations
- NEB transition state searches
"""

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    PreflightRequirement,
    ErrorClass,
)


class VASPDriver(BaseEngineDriver):
    """VASP driver bundle implementing the EngineDriver protocol."""

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "vasp"

    @property
    def display_name(self) -> str:
        return "VASP"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return VASP step type specifications."""
        return [
            StepTypeSpec(
                id="vasp_scf",
                engine="vasp",
                executable="vasp_std",
                description="VASP SCF calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_relax",
                engine="vasp",
                executable="vasp_std",
                description="VASP ionic relaxation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_vc_relax",
                engine="vasp",
                executable="vasp_std",
                description="VASP variable-cell relaxation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_md",
                engine="vasp",
                executable="vasp_std",
                description="VASP molecular dynamics",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                id="vasp_bands",
                engine="vasp",
                executable="vasp_std",
                description="VASP band structure calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_dos",
                engine="vasp",
                executable="vasp_std",
                description="VASP density of states (explicit step type, not mapped from GEN_DOS)",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_static",
                engine="vasp",
                executable="vasp_std",
                description="VASP static calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_neb",
                engine="vasp",
                executable="vasp_std",
                description="VASP NEB transition state search",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                id="vasp_phonon",
                engine="vasp",
                executable="vasp_std",
                description="VASP phonon calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_elastic",
                engine="vasp",
                executable="vasp_std",
                description="VASP elastic constants",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_dielectric",
                engine="vasp",
                executable="vasp_std",
                description="VASP dielectric properties",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return VASP step handler."""
        from .handler import vasp_step_handler
        return vasp_step_handler

    def get_recipe_class(self):
        """Return VASP recipe class."""
        from .recipe import VASPRecipe
        return VASPRecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return VASP GEN→SPEC mappings.
        
        Note: GEN_DOS is a zero-mapping (integrated in NSCF output).
        """
        return {
            "GEN_SCF": "vasp_scf",
            "GEN_RELAX": "vasp_relax",
            "GEN_VC_RELAX": "vasp_vc_relax",
            "GEN_MD": "vasp_md",
            "GEN_BANDS": "vasp_bands",
            # GEN_DOS is zero-mapping (integrated in NSCF output, no separate step)
        }

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where VASP differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """VASP uses cleanup policy (fresh workdir each step)."""
        return WorkdirPolicy.CLEANUP

    def get_capabilities(self) -> set[str]:
        """VASP capabilities."""
        return {
            "scf", "relax", "md", "bands", "dos",
            "phonon", "elastic", "dielectric", "neb",
            "periodic", "mpi", "gpu",
            "charge_continuation", "wfn_continuation",
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        """MD steps should not be skipped."""
        if step_type == "vasp_md":
            return False
        return True

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        """VASP preflight requirements (CHGCAR, WAVECAR)."""
        requirements = []

        # Check step configuration for continuation
        step_config = getattr(step, "config", {}) or {}

        if step_config.get("use_chgcar", False):
            requirements.append(PreflightRequirement(
                artifact_type="CHGCAR",
                source_step=step_config.get("chgcar_source"),
                required=True,
                description="Charge density for continuation",
            ))

        if step_config.get("use_wavecar", False):
            requirements.append(PreflightRequirement(
                artifact_type="WAVECAR",
                source_step=step_config.get("wavecar_source"),
                required=False,  # WAVECAR is optional optimization
                description="Wavefunction for continuation",
            ))

        return requirements

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify VASP errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "scf convergence" in stderr_lower or "electronic convergence" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "out of memory" in stderr_lower or "malloc" in stderr_lower:
            return ErrorClass.MEMORY
        if "timeout" in stderr_lower or exit_code == 124:
            return ErrorClass.TIMEOUT
        if "potcar" in stderr_lower and "not found" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "incar" in stderr_lower and "error" in stderr_lower:
            return ErrorClass.INPUT_ERROR

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """VASP artifact patterns for discovery."""
        return {
            "CHGCAR": "CHGCAR*",
            "WAVECAR": "WAVECAR",
            "OUTCAR": "OUTCAR",
            "vasprun": "vasprun.xml",
            "CONTCAR": "CONTCAR",
            "OSZICAR": "OSZICAR",
            "DOSCAR": "DOSCAR",
            "EIGENVAL": "EIGENVAL",
            "PROCAR": "PROCAR",
        }

    def find_latest_artifact(self, workdir, artifact_type: str):
        """Find latest artifact in workdir."""
        from pathlib import Path
        import glob

        pattern = self.get_artifact_patterns().get(artifact_type)
        if not pattern:
            return None

        matches = sorted(
            Path(workdir).glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return matches[0] if matches else None

