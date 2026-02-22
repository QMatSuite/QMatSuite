"""QMCPACK engine driver.

This driver handles all QMCPACK Quantum Monte Carlo calculations including:
- Variational Monte Carlo (VMC)
- Diffusion Monte Carlo (DMC)
- Wavefunction optimization
"""

from qmatsuite.core.analysis.capability import AnalysisCapability
from qmatsuite.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    ErrorClass,
)


class QMCPACKDriver(BaseEngineDriver):
    """QMCPACK driver bundle implementing the EngineDriver protocol."""

    PREFIX: str = "qmcpack"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "vmc", "dmc", "wfopt"
    })
    ENGINE_ROLE: str = "postprocessing"
    COMPANION_ENGINES: frozenset = frozenset()
    ANALYSIS_CAPABILITIES = [
        AnalysisCapability(
            object_type="convergence",
            gen_step_sequence=["vmc"],
            evidence_files=["*.scalar.dat"],
        ),
        AnalysisCapability(
            object_type="convergence",
            gen_step_sequence=["dmc"],
            evidence_files=["*.scalar.dat"],
        ),
    ]

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "qmcpack"

    @property
    def display_name(self) -> str:
        return "QMCPACK"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return QMCPACK step type specifications."""
        return [
            StepTypeSpec(
                step_type_spec="qmcpack_vmc",
                engine="qmcpack",
                executable="qmcpack",
                description="QMCPACK Variational Monte Carlo",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="qmcpack_dmc",
                engine="qmcpack",
                executable="qmcpack",
                description="QMCPACK Diffusion Monte Carlo",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                step_type_spec="qmcpack_wfopt",
                engine="qmcpack",
                executable="qmcpack",
                description="QMCPACK wavefunction optimization",
                category="calculation",
                mpi_aware=True,
            ),
        ]

    def get_handler(self):
        """Return QMCPACK step handler."""
        from .handler import qmcpack_step_handler
        return qmcpack_step_handler

    def get_recipe_class(self):
        """Return QMCPACK recipe class."""
        from .recipe import QMCPACKRecipe
        return QMCPACKRecipe

    def get_input_spec(self, **context):
        """Return QMCPACK input format specification."""
        from .inputspec import get_qmcpack_input_spec
        return get_qmcpack_input_spec(**context)

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where QMCPACK differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """QMCPACK uses isolated workdir per step."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """QMCPACK capabilities."""
        return {
            "vmc", "dmc", "wfopt",
            "periodic", "molecular", "mpi",
            "qmc",  # Quantum Monte Carlo
        }

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify QMCPACK errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "out of memory" in stderr_lower or "malloc" in stderr_lower:
            return ErrorClass.MEMORY
        if "timeout" in stderr_lower or exit_code == 124:
            return ErrorClass.TIMEOUT
        if "cannot open" in stderr_lower or "file not found" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "qmcpack" in stderr_lower and "not found" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """QMCPACK artifact patterns for discovery."""
        return {
            "scalar": "*.scalar.dat",
            "dmc": "*.dmc.dat",
            "opt": "*.opt.xml",
            "input": "*.xml",
            "hdf5": "*.h5",
        }
