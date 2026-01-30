"""ORCA engine driver.

This driver handles all ORCA quantum chemistry calculations including:
- SCF, geometry optimization, frequency calculations
- MP2, CCSD, CASSCF, NEVPT2 methods
- TD-DFT excited state calculations
"""

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    ErrorClass,
)


class ORCADriver(BaseEngineDriver):
    """ORCA driver bundle implementing the EngineDriver protocol."""

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "orca"

    @property
    def display_name(self) -> str:
        return "ORCA"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return ORCA step type specifications."""
        return [
            StepTypeSpec(
                step_type_spec="orca_scf",
                engine="orca",
                executable="orca",
                description="ORCA SCF single-point calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_opt",
                engine="orca",
                executable="orca",
                description="ORCA geometry optimization",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_freq",
                engine="orca",
                executable="orca",
                description="ORCA frequency/vibrational calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_sp",
                engine="orca",
                executable="orca",
                description="ORCA single-point energy",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_tddft",
                engine="orca",
                executable="orca",
                description="ORCA TD-DFT excited states",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_mp2",
                engine="orca",
                executable="orca",
                description="ORCA MP2 calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_ccsd",
                engine="orca",
                executable="orca",
                description="ORCA CCSD calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_casscf",
                engine="orca",
                executable="orca",
                description="ORCA CASSCF calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_nevpt2",
                engine="orca",
                executable="orca",
                description="ORCA NEVPT2 calculation",
                category="calculation",
            ),
            # Also include step types that exist in registry
            StepTypeSpec(
                step_type_spec="orca_hf",
                engine="orca",
                executable="orca",
                description="ORCA Hartree-Fock calculation",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_td",
                engine="orca",
                executable="orca",
                description="ORCA TDDFT/CIS excited states",
                category="calculation",
            ),
            StepTypeSpec(
                step_type_spec="orca_relax",
                engine="orca",
                executable="orca",
                description="ORCA geometry optimization",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return ORCA chain handler."""
        from .handler import orca_chain_handler
        return orca_chain_handler

    def get_recipe_class(self):
        """Return ORCA recipe class."""
        from .recipe import ORCARecipe
        return ORCARecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return ORCA GEN→SPEC mappings.

        This is the SSOT for ORCA step-type mappings.
        """
        return {
            "GEN_SCF": "orca_scf",
            "GEN_HF": "orca_hf",
            "GEN_OPT": "orca_opt",
            "GEN_RELAX": "orca_relax",
            "GEN_FREQ": "orca_freq",
            "GEN_SP": "orca_sp",
            "GEN_TD": "orca_td",
            "GEN_TDDFT": "orca_tddft",
            "GEN_MP2": "orca_mp2",
            "GEN_CCSD": "orca_ccsd",
            "GEN_CASSCF": "orca_casscf",
            "GEN_NEVPT2": "orca_nevpt2",
        }

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where ORCA differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """ORCA uses isolated workdir (default)."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """ORCA capabilities."""
        return {
            "scf", "opt", "freq", "sp",
            "tddft", "mp2", "ccsd", "casscf", "nevpt2",
            "molecular", "mpi",
            "chain",  # Supports chain execution
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        """All ORCA steps can be skipped if done."""
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify ORCA errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "scf not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "out of memory" in stderr_lower or "allocation" in stderr_lower:
            return ErrorClass.MEMORY
        if "input error" in stderr_lower or "unknown keyword" in stderr_lower:
            return ErrorClass.INPUT_ERROR
        if "orca not found" in stderr_lower or exit_code == 127:
            return ErrorClass.EXECUTABLE_NOT_FOUND

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """ORCA artifact patterns for discovery."""
        return {
            "output": "*.out",
            "gbw": "*.gbw",
            "xyz": "*.xyz",
            "hess": "*.hess",
            "prop": "*.prop",
            "engrad": "*.engrad",
        }

