"""QE Driver (stub for migration)."""

from quantumvitas.core.driver_protocol import BaseEngineDriver, StepTypeSpec, WorkdirPolicy


class QEDriver(BaseEngineDriver):
    """QE driver stub - delegates to qe_shim during migration."""

    @property
    def engine_family(self) -> str:
        return "qe"

    @property
    def display_name(self) -> str:
        return "Quantum ESPRESSO"

    @property
    def driver_api_version(self) -> str:
        return "2.0.0-alpha"

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
        from quantumvitas.drivers.qe_shim import QELegacyDriver
        return QELegacyDriver().get_materialization_map()

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.SHARED

