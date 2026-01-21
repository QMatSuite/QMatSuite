"""
Engine Recipes: Materialization strategies for different engine types.

This module implements the three recipe patterns:
1. QE-Recipe: Directory-state, one job per step
2. ORCA-Recipe: QC strong-chain, one job per subchain
3. PySCF-Recipe: QC weak-chain/session, one job per subchain

Per engine_recipes_jobgraph_plan.md (Constitution):
- Recipes materialize JobGraphs from calculation steps
- JobGraph is runtime-only (NOT persisted)
- Working directories and scratch dirs follow engine filesystem contracts
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Protocol, runtime_checkable

from quantumvitas.execution.job_graph import Job, JobGraph, compute_job_fingerprint
from quantumvitas.workflow.registry import (
    get_registry,
    generate_subchain_basename,
    get_chain_namespace_folder,
)
from quantumvitas.engine.qc_engine_base import SCF_ROOT_TYPES, RELAX_STEP_TYPES
from quantumvitas.core.driver_registry import DriverRegistry

if TYPE_CHECKING:
    from quantumvitas.calculation.step import Step


class TopologyError(Exception):
    """Raised when step topology violates QC chain rules."""
    pass


def verify_qc_topology(steps: List["Step"], registry) -> None:
    """
    Verify QC topology before execution.
    
    Rules:
    - Relax steps are standalone (length=1 chains)
    - Non-relax, non-SCF steps must trace to SCF root without crossing relax
    
    Args:
        steps: List of Step objects to verify
        registry: StepTypeRegistry instance
        
    Raises:
        TopologyError: If topology is invalid
    """
    for i, step in enumerate(steps):
        # Get step type (try public_type first, fallback to step_type)
        step_type = getattr(step, 'public_type', None) or getattr(step, 'step_type', None)
        if not step_type:
            continue
        
        # Look up spec to get public_type
        spec = registry.get(step_type)
        if spec:
            step_public_type = spec.public_type
        else:
            # Fallback: assume step_type is already public_type
            step_public_type = step_type
        
        if step_public_type in RELAX_STEP_TYPES:
            continue  # Relax is standalone, always valid
        
        if step_public_type in SCF_ROOT_TYPES:
            continue  # SCF root starts new chain, always valid
        
        # Non-relax, non-SCF: must find SCF ancestor without intervening relax
        found_scf = False
        for j in range(i - 1, -1, -1):
            ancestor_step = steps[j]
            ancestor_type = getattr(ancestor_step, 'public_type', None) or getattr(ancestor_step, 'step_type', None)
            if not ancestor_type:
                continue
            
            ancestor_spec = registry.get(ancestor_type)
            if ancestor_spec:
                ancestor_public_type = ancestor_spec.public_type
            else:
                ancestor_public_type = ancestor_type
            
            if ancestor_public_type in RELAX_STEP_TYPES:
                step_name = getattr(step, 'name', f'step_{i}') or f'step_{i}'
                raise TopologyError(
                    f"TOPOLOGY_ERROR: Step '{step_name}' (index {i}) cannot trace to SCF root. "
                    f"A relax step at index {j} blocks the dependency chain. "
                    "Relax steps are not electronic state providers; they must be in standalone chains."
                )
            if ancestor_public_type in SCF_ROOT_TYPES:
                found_scf = True
                break
        
        if not found_scf:
            step_name = getattr(step, 'name', f'step_{i}') or f'step_{i}'
            raise TopologyError(
                f"TOPOLOGY_ERROR: Step '{step_name}' (index {i}) requires SCF root but none found. "
                "Add an SCF step before this step."
            )


@runtime_checkable
class Recipe(Protocol):
    """
    Protocol for engine recipes.

    A recipe knows how to materialize a JobGraph from calculation steps.
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize a JobGraph from calculation steps.

        Args:
            steps: List of Step objects to materialize
            calc_raw_dir: Path to calculation raw directory (calc/raw/)
            step_shas: Optional dict of step_ulid -> SHA256 for fingerprinting

        Returns:
            JobGraph with jobs ready for execution
        """
        ...


class BaseRecipe(ABC):
    """Base class for recipe implementations."""

    @abstractmethod
    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """Materialize a JobGraph from calculation steps."""
        pass

    def _get_step_sha(
        self, step: "Step", step_shas: Optional[Dict[str, str]]
    ) -> Optional[str]:
        """Get SHA for a step from the provided map."""
        if step_shas is None:
            return None
        return step_shas.get(step.meta.id)


class QERecipe(BaseRecipe):
    """
    QE-Recipe: Directory-state, step-run model.

    Creates one job per step. Jobs share the same working directory
    and scratch directory (outdir/).

    Used by: QE, Wannier90, future VASP, ABINIT
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize one job per QE step.

        Args:
            steps: List of QE steps
            calc_raw_dir: Path to calc/raw/
            step_shas: Optional dict for fingerprinting

        Returns:
            JobGraph with one job per step
        """
        registry = get_registry()
        jobs: List[Job] = []

        for idx, step in enumerate(steps):
            job_id = f"step_{idx:02d}"

            # Get step type info from registry
            step_type = step.step_type
            spec = registry.get(str(step_type)) if step_type else None

            # Determine executable and input file
            if spec:
                executable = spec.executable
                public_type = spec.public_type
            else:
                executable = "pw.x"
                public_type = str(step_type) if step_type else "custom"

            # Input file uses GEN naming (per Constitution §F)
            input_file = f"{public_type}.in"

            # Build command
            command = [executable, input_file]

            # Expected outputs (GEN naming)
            expected_outputs = [calc_raw_dir / f"{public_type}.out"]

            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None

            # Create job
            job = Job(
                id=job_id,
                step_ids=[step.meta.id],
                working_dir=calc_raw_dir,
                command=command,
                input_files=[calc_raw_dir / input_file],
                expected_outputs=expected_outputs,
                deps=[],  # Conservative: no explicit deps, use prefix selection
                fingerprint=fingerprint,
                metadata={
                    "engine": "qe",
                    "spec_step_type": spec.machine_type if spec else None,
                    "public_type": public_type,
                    "scratch_dir": calc_raw_dir / "outdir",
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)


def get_recipe_for_engine(engine_family: str) -> BaseRecipe:
    """
    Get the appropriate recipe for an engine family via registry.

    Args:
        engine_family: Engine family name ("qe", "orca", "pyscf")

    Returns:
        Recipe instance for the engine family

    Raises:
        UnknownEngineError: If engine family is unknown
    """
    # Ensure drivers are loaded
    import quantumvitas.drivers

    recipe_class = DriverRegistry.get_recipe_class(engine_family)
    return recipe_class()


# Backward-compatibility re-exports for migrated recipe classes
# These recipes were moved to driver bundles but are re-exported here
# to maintain compatibility with existing test code and handlers.
# The DriverRegistry is the primary mechanism; these are compat shims.
# Import at module level to ensure isinstance() checks work correctly
from quantumvitas.drivers.qe.recipe import QERecipe
from quantumvitas.drivers.orca.recipe import ORCARecipe
from quantumvitas.drivers.vasp.recipe import VASPRecipe
from quantumvitas.drivers.pyscf.recipe import PySCFRecipe
from quantumvitas.drivers.cp2k.recipe import CP2KRecipe
from quantumvitas.drivers.lammps.recipe import LAMMPSRecipe
from quantumvitas.drivers.w90.recipe import W90Recipe

__all__ = [
    "BaseRecipe",
    "get_recipe_for_engine",
    "QERecipe",
    "ORCARecipe",
    "VASPRecipe",
    "PySCFRecipe",
    "CP2KRecipe",
    "LAMMPSRecipe",
    "W90Recipe",
]
