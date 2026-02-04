"""Psi4 engine driver.

This driver handles all Psi4 quantum chemistry calculations including:
- HF/DFT SCF calculations
- MP2 correlated methods
- Geometry optimization
- TDDFT excited states
"""

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    ErrorClass,
)


class Psi4Driver(BaseEngineDriver):
    """Psi4 driver bundle implementing the EngineDriver protocol."""

    PREFIX: str = "psi4"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "hf", "mp2", "relax", "td"
    })

    @property
    def engine_family(self) -> str:
        return "psi4"

    @property
    def display_name(self) -> str:
        return "Psi4"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return Psi4 step type specifications."""
        return [
            StepTypeSpec(
                step_type_spec="psi4_scf",
                engine="psi4",
                executable="python",
                description="Psi4 HF/DFT SCF calculation",
                category="calculation",
                mpi_aware=False,
            ),
            StepTypeSpec(
                step_type_spec="psi4_hf",
                engine="psi4",
                executable="python",
                description="Psi4 Hartree-Fock calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="psi4_mp2",
                engine="psi4",
                executable="python",
                description="Psi4 MP2 calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="psi4_relax",
                engine="psi4",
                executable="python",
                description="Psi4 geometry optimization",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="psi4_td",
                engine="psi4",
                executable="python",
                description="Psi4 TDDFT/TDA excited states",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return Psi4 chain handler."""
        from .handler import psi4_chain_handler
        return psi4_chain_handler

    def get_recipe_class(self):
        """Return Psi4 recipe class."""
        from .recipe import Psi4Recipe
        return Psi4Recipe

    def get_workdir_policy(self) -> WorkdirPolicy:
        """Psi4 uses isolated workdir."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """Psi4 capabilities."""
        return {
            "scf", "dft", "hf", "relax",
            "mp2", "tddft",
            "molecular",
            "chain",
            "python_native",
        }

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        """All Psi4 steps can be skipped if done."""
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify Psi4 errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "convergence" in stderr_lower or "not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "memory" in stderr_lower or "memoryerror" in stderr_lower:
            return ErrorClass.MEMORY
        if "import" in stderr_lower and "psi4" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND
        if "keyerror" in stderr_lower or "valueerror" in stderr_lower:
            return ErrorClass.INPUT_ERROR

        return ErrorClass.UNKNOWN

    def get_artifact_patterns(self) -> dict[str, str]:
        """Psi4 artifact patterns for discovery."""
        return {
            "wavefunction": "*.npy",
            "output": "*.dat",
            "results": "results.json",
        }
