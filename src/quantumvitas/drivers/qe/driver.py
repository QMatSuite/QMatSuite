"""QE Driver."""

from quantumvitas.core.analysis.capability import AnalysisCapability
from quantumvitas.core.driver_protocol import BaseEngineDriver, StepTypeSpec, WorkdirPolicy


class QEDriver(BaseEngineDriver):
    """QE driver bundle implementing the EngineDriver protocol."""

    PREFIX: str = "qe"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "nscf", "relax", "bands", "bandspw", "dos",
        "pw2wannier", "ph", "gipaw", "md", "custom"
    })
    ENGINE_ROLE: str = "base"
    COMPANION_ENGINES: frozenset = frozenset({"w90", "qmcpack", "yambo"})
    ANALYSIS_CAPABILITIES = [
        AnalysisCapability(
            object_type="bands",
            gen_step_sequence=["bandspw"],
            evidence_files=["*.bands.dat.gnu"],
        ),
        AnalysisCapability(
            object_type="trajectory",
            gen_step_sequence=["relax"],
            evidence_files=["*.relax.out"],
        ),
    ]

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

    def get_input_spec(self, **context):
        """Return QE input format specification."""
        from .inputspec import get_qe_input_spec
        return get_qe_input_spec(**context)

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.SHARED
