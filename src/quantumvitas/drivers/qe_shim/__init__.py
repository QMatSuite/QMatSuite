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
        # Delegate to new driver
        from quantumvitas.drivers.qe.step_types import QE_STEP_TYPE_SPECS
        return QE_STEP_TYPE_SPECS

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

