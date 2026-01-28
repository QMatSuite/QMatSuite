"""QE Driver."""

from quantumvitas.core.driver_protocol import BaseEngineDriver, StepTypeSpec, WorkdirPolicy


class QEDriver(BaseEngineDriver):
    """QE driver bundle implementing the EngineDriver protocol."""

    @property
    def engine_family(self) -> str:
        return "qe"

    @property
    def display_name(self) -> str:
        return "Quantum ESPRESSO"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        from .step_types import QE_STEP_TYPE_SPECS
        return QE_STEP_TYPE_SPECS

    def get_handler(self):
        from .handler import qe_step_handler
        return qe_step_handler

    def get_recipe_class(self):
        from .recipe import QERecipe
        return QERecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return QE materialization mappings.

        Maps generalized types (GEN_*) to QE-specific types.
        This is the SSOT for QE step-type mappings.

        Note: GEN_WANNIER maps to w90_run which is a separate engine (w90).
        Cross-engine mappings are handled via workflow orchestration, not here.
        """
        return {
            "GEN_SCF": "qe_scf",
            "GEN_NSCF": "qe_nscf",
            "GEN_RELAX": "qe_relax",
            "GEN_VC_RELAX": "qe_relax",  # Maps to same step type
            "GEN_BANDS": "qe_bands_pw",
            "GEN_BANDS_POST": "qe_bands",
            "GEN_DOS": "qe_dos",
            "GEN_WANNIER_CONVERT": "qe_pw2wannier90",
            # GEN_WANNIER is handled by w90 driver, not QE
            "GEN_PHONON": "qe_ph",
            "GEN_MD": "qe_md",
            "GEN_VC_MD": "qe_vc_md",
            "GEN_CUSTOM": "qe_custom",
        }

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.SHARED

