"""QE legacy shim driver.

This is a minimal driver that wraps existing QE code in the driver interface.
It allows QE to work with the new registry system without full migration.

This shim will be replaced when QE is properly migrated in a future effort.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import BaseEngineDriver, StepTypeSpec, WorkdirPolicy


class QELegacyDriver(BaseEngineDriver):
    """Legacy QE driver wrapping existing implementation.

    This is a shim that:
    1. Registers QE step types with the registry
    2. Points to existing handler/recipe implementations
    3. Will be replaced by proper QE driver in future migration
    """

    @property
    def engine_family(self) -> str:
        return "qe"

    @property
    def display_name(self) -> str:
        return "Quantum ESPRESSO (Legacy)"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return QE step types.

        These are copied from the existing workflow/registry.py.
        """
        return [
            StepTypeSpec(
                id="qe_scf",
                engine="qe",
                executable="pw.x",
                description="QE SCF calculation",
            ),
            StepTypeSpec(
                id="qe_relax",
                engine="qe",
                executable="pw.x",
                description="QE relaxation",
            ),
            StepTypeSpec(
                id="qe_vc_relax",
                engine="qe",
                executable="pw.x",
                description="QE variable-cell relaxation",
            ),
            StepTypeSpec(
                id="qe_bands",
                engine="qe",
                executable="bands.x",
                description="QE band structure",
            ),
            StepTypeSpec(
                id="qe_bands_pw",
                engine="qe",
                executable="pw.x",
                description="QE band structure (pw.x)",
            ),
            StepTypeSpec(
                id="qe_nscf",
                engine="qe",
                executable="pw.x",
                description="QE non-self-consistent calculation",
            ),
            StepTypeSpec(
                id="qe_dos",
                engine="qe",
                executable="dos.x",
                description="QE density of states",
            ),
            StepTypeSpec(
                id="qe_pdos",
                engine="qe",
                executable="projwfc.x",
                description="QE projected density of states",
            ),
            StepTypeSpec(
                id="qe_ph",
                engine="qe",
                executable="ph.x",
                description="QE phonon calculation",
            ),
            StepTypeSpec(
                id="qe_q2r",
                engine="qe",
                executable="q2r.x",
                description="QE q2r transformation",
            ),
            StepTypeSpec(
                id="qe_matdyn",
                engine="qe",
                executable="matdyn.x",
                description="QE matdyn calculation",
            ),
            StepTypeSpec(
                id="qe_dynmat",
                engine="qe",
                executable="dynmat.x",
                description="QE dynmat calculation",
            ),
            StepTypeSpec(
                id="qe_pp",
                engine="qe",
                executable="pp.x",
                description="QE post-processing",
            ),
            StepTypeSpec(
                id="qe_plotband",
                engine="qe",
                executable="plotband.x",
                description="QE band plotting",
            ),
            StepTypeSpec(
                id="qe_hp",
                engine="qe",
                executable="hp.x",
                description="QE Hubbard parameters",
            ),
            StepTypeSpec(
                id="qe_md",
                engine="qe",
                executable="pw.x",
                description="QE molecular dynamics",
            ),
            StepTypeSpec(
                id="qe_vc_md",
                engine="qe",
                executable="pw.x",
                description="QE variable-cell molecular dynamics",
            ),
            StepTypeSpec(
                id="qe_pw2wannier90",
                engine="qe",
                executable="pw2wannier90.x",
                description="QE to Wannier90 interface",
            ),
            StepTypeSpec(
                id="qe_custom",
                engine="qe",
                executable="pw.x",
                description="Custom step type (escape hatch)",
            ),
            # Wannier90 preprocessing (runs within QE context)
            # Note: w90_run is now handled by w90 driver, only w90_preproc remains here
            StepTypeSpec(
                id="w90_preproc",
                engine="qe",
                executable="pw2wannier90.x",
                description="Wannier90 preprocessing",
            ),
        ]

    def get_handler(self):
        """Return existing QE handler."""
        from quantumvitas.execution.handlers import qe_step_handler
        return qe_step_handler

    def get_recipe_class(self):
        """Return existing QE recipe."""
        from quantumvitas.execution.recipes import QERecipe
        return QERecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return QE materialization mappings.

        Maps generalized types (GEN_*) to QE-specific types.
        """
        return {
            "GEN_SCF": "qe_scf",
            "GEN_RELAX": "qe_relax",
            "GEN_BANDS": "qe_bands_pw",
            "GEN_DOS": "qe_dos",
        }

    def get_workdir_policy(self) -> WorkdirPolicy:
        """QE uses shared outdir model."""
        return WorkdirPolicy.SHARED


# Register at import time
DriverRegistry.register(QELegacyDriver())

