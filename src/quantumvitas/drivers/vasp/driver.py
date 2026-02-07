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

    PREFIX: str = "vasp"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "nscf", "relax", "md", "bandspw"
    })
    ENGINE_ROLE: str = "base"
    COMPANION_ENGINES: frozenset = frozenset()

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
                step_type_spec="vasp_scf",
                engine="vasp",
                executable="vasp_std",
                description="VASP SCF calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="vasp_nscf",
                engine="vasp",
                executable="vasp_std",
                description="VASP non-self-consistent calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="vasp_relax",
                engine="vasp",
                executable="vasp_std",
                description="VASP ionic relaxation",
                category="calculation",
            ),
            # Removed: vasp_vc_relax - VC is a parameter, not a separate step type
            # Use vasp_relax with ISIF=3 parameter instead
            StepTypeSpec(
                step_type_spec="vasp_md",
                engine="vasp",
                executable="vasp_std",
                description="VASP molecular dynamics",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                step_type_spec="vasp_bandspw",
                engine="vasp",
                executable="vasp_std",
                description="VASP band structure calculation (eigenstates along k-path)",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="vasp_dos",
                engine="vasp",
                executable="vasp_std",
                description="VASP density of states (explicit step type, not mapped from gen step 'dos')",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="vasp_static",
                engine="vasp",
                executable="vasp_std",
                description="VASP static calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="vasp_neb",
                engine="vasp",
                executable="vasp_std",
                description="VASP NEB transition state search",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="vasp_phonon",
                engine="vasp",
                executable="vasp_std",
                description="VASP phonon calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="vasp_elastic",
                engine="vasp",
                executable="vasp_std",
                description="VASP elastic constants",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="vasp_dielectric",
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


    def get_input_spec(self, **context):
        """Return VASP input format specification."""
        from .inputspec import get_vasp_input_spec
        return get_vasp_input_spec(**context)

    def _get_zero_mappings(self) -> set[str]:
        """Return gen steps that are explicit zero-mappings (no step needed).

        These are operations that VASP handles implicitly in other steps.
        Note: This method is deprecated. Zero-mappings are now determined by
        absence from SUPPORTED_GEN_STEPS.
        """
        return {
            "dos",        # DOS integrated in NSCF output
            "bands",      # VASP doesn't need post-processing (bands.x equivalent)
            "dospp",      # VASP doesn't need dos.x post-processing
            "bandspp",    # VASP doesn't need bands.x post-processing
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

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        """MD steps should not be skipped."""
        if step_type_spec == "vasp_md":
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

