"""PySCF engine driver.

This driver handles all PySCF quantum chemistry calculations including:
- HF/DFT SCF calculations
- Geometry optimization, frequency calculations
- MP2, CCSD correlated methods
- CASSCF, CASCI multiconfigurational methods
- TD-DFT excited states
"""

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    ErrorClass,
)


class PySCFDriver(BaseEngineDriver):
    """PySCF driver bundle implementing the EngineDriver protocol."""

    PREFIX: str = "pyscf"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "relax", "mp2", "td"
    })

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "pyscf"

    @property
    def display_name(self) -> str:
        return "PySCF"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return PySCF step type specifications."""
        return [
            StepTypeSpec(
                step_type_spec="pyscf_scf",
                engine="pyscf",
                executable="python",  # PySCF is Python-based
                description="PySCF HF/DFT SCF calculation",
                category="calculation",
                mpi_aware=False,  # PySCF uses internal parallelization
            ),
            StepTypeSpec(
                step_type_spec="pyscf_dft",
                engine="pyscf",
                executable="python",
                description="PySCF DFT calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="pyscf_opt",
                engine="pyscf",
                executable="python",
                description="PySCF geometry optimization",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="pyscf_freq",
                engine="pyscf",
                executable="python",
                description="PySCF frequency calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="pyscf_mp2",
                engine="pyscf",
                executable="python",
                description="PySCF MP2 calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="pyscf_ccsd",
                engine="pyscf",
                executable="python",
                description="PySCF CCSD calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="pyscf_casscf",
                engine="pyscf",
                executable="python",
                description="PySCF CASSCF calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="pyscf_casci",
                engine="pyscf",
                executable="python",
                description="PySCF CASCI calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="pyscf_tddft",
                engine="pyscf",
                executable="python",
                description="PySCF TD-DFT calculation",
                category="calculation",
            ),
            # Also include step types that exist in registry
            StepTypeSpec(
                step_type_spec="pyscf_td",
                engine="pyscf",
                executable="python",
                description="PySCF TDDFT/CIS excited states",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="pyscf_relax",
                engine="pyscf",
                executable="python",
                description="PySCF geometry optimization",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return PySCF chain handler."""
        from .handler import pyscf_chain_handler
        return pyscf_chain_handler

    def get_recipe_class(self):
        """Return PySCF recipe class."""
        from .recipe import PySCFRecipe
        return PySCFRecipe

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where PySCF differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """PySCF uses isolated workdir (default)."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """PySCF capabilities."""
        return {
            "scf", "dft", "opt", "freq",
            "mp2", "ccsd", "casscf", "casci", "tddft",
            "molecular",  # PySCF is primarily molecular
            "chain",  # Supports chain execution
            "python_native",  # Python-based, no external executable
        }

    def supports_incremental_skip(self, step_type_spec: str) -> bool:
        """All PySCF steps can be skipped if done."""
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify PySCF errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "scf not converged" in stderr_lower or "convergence" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "memory" in stderr_lower or "memoryerror" in stderr_lower:
            return ErrorClass.MEMORY
        if "import" in stderr_lower and "pyscf" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND
        if "keyerror" in stderr_lower or "valueerror" in stderr_lower:
            return ErrorClass.INPUT_ERROR

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """PySCF artifact patterns for discovery."""
        return {
            "chkfile": "*.chk",
            "output": "*.out",
            "molden": "*.molden",
            "cube": "*.cube",
        }

