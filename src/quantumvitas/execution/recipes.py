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


class VASPRecipe(BaseRecipe):
    """
    VASP-Recipe: Directory-state, one job per step (isolated workdirs).
    
    Creates one job per step. Each step runs in its own isolated workdir:
    `calc/raw/<step_ulid>/`
    
    Working directory is completely cleaned before execution (rm -rf).
    Artifacts (CHGCAR/WAVECAR) are copied from reference SCF step.
    
    Used by: VASP
    """
    
    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize jobs for VASP steps.
        
        Each step gets its own isolated workdir: calc_raw_dir / step_ulid
        
        Args:
            steps: List of VASP steps
            calc_raw_dir: Path to calc/raw/
            step_shas: Optional dict for fingerprinting
        
        Returns:
            JobGraph with one job per step
        """
        if not steps:
            return JobGraph(jobs=[])
        
        registry = get_registry()
        jobs: List[Job] = []
        
        for step in steps:
            # Get step type info
            step_type = step.step_type
            spec = registry.get(step_type) if step_type else None
            public_type = spec.public_type if spec else "unknown"
            
            # Job ID = step ULID
            job_id = step.meta.id
            
            # Working directory: isolated per step
            working_dir = calc_raw_dir / step.meta.id
            
            # VASP executable (from spec)
            executable = spec.executable if spec else "vasp_std"
            
            # Command: just the executable (VASP reads POSCAR/INCAR/KPOINTS/POTCAR from CWD)
            command = [executable]
            
            # Input files (will be materialized into working_dir)
            input_files = [
                working_dir / "POSCAR",
                working_dir / "INCAR",
                working_dir / "KPOINTS",
                working_dir / "POTCAR",
            ]
            
            # Expected outputs
            expected_outputs = [
                working_dir / "OUTCAR",
                working_dir / "OSZICAR",
            ]
            
            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None
            
            # Dependencies: linear (each step depends on previous)
            deps = []
            if len(jobs) > 0:
                deps = [jobs[-1].id]
            
            # Create job
            job = Job(
                id=job_id,
                step_ids=[step.meta.id],
                working_dir=working_dir,
                command=command,
                input_files=input_files,
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=fingerprint,
                metadata={
                    "engine": "vasp",
                    "spec_step_type": spec.machine_type if spec else None,
                    "public_type": public_type,
                },
            )
            jobs.append(job)
        
        return JobGraph(jobs=jobs)


class ORCARecipe(BaseRecipe):
    """
    ORCA-Recipe: QC strong-chain model.

    Creates one job per subchain. Each job executes a fused ORCA input
    containing all steps from SCF root to target.

    Working directory: calc/raw/scf_<suffix>/
    Canonical orbitals: scf.gbw
    Subchain files: s.inp, s_t.inp, s_m2.inp (stable tokens)

    Used by: ORCA
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize subchain jobs for ORCA.

        For a chain [SCF, MP2, TD], creates:
        - Job "s": SCF only
        - Job "s_m2": SCF + MP2
        - Job "s_t": SCF + TD

        Args:
            steps: List of ORCA steps (first should be SCF)
            calc_raw_dir: Path to calc/raw/
            step_shas: Optional dict for fingerprinting

        Returns:
            JobGraph with subchain jobs
        """
        if not steps:
            return JobGraph(jobs=[])

        registry = get_registry()
        
        # Verify topology before materialization
        verify_qc_topology(steps, registry)
        jobs: List[Job] = []

        # Get SCF root info for namespace folder
        scf_root = steps[0]
        scf_ulid = scf_root.meta.id
        namespace_folder = get_chain_namespace_folder(scf_ulid)
        working_dir = calc_raw_dir / namespace_folder

        # Build subchain for each step
        for target_idx, target_step in enumerate(steps):
            # Get public types for all steps in subchain
            subchain_steps = steps[: target_idx + 1]
            public_types = []

            for s in subchain_steps:
                spec = (
                    registry.get(str(s.step_type))
                    if s.step_type
                    else None
                )
                pt = spec.public_type if spec else "scf"
                public_types.append(pt)

            # Generate subchain basename from stable tokens
            try:
                basename = generate_subchain_basename(public_types)
            except ValueError:
                # Fallback if token not defined
                basename = "_".join(public_types)

            # Collect step IDs and SHAs for fingerprint
            step_ids = [s.meta.id for s in subchain_steps]
            step_sha_list = [
                self._get_step_sha(s, step_shas) or ""
                for s in subchain_steps
            ]
            fingerprint = compute_job_fingerprint(
                [sha for sha in step_sha_list if sha]
            )

            # Input/output files (GEN naming via stable tokens)
            input_file = working_dir / f"{basename}.inp"
            output_file = working_dir / f"{basename}.out"
            property_file = working_dir / f"{basename}.property.txt"
            gbw_file = working_dir / "scf.gbw"

            # Create job
            job = Job(
                id=basename,
                step_ids=step_ids,
                working_dir=working_dir,
                command=["orca", f"{basename}.inp"],
                input_files=[input_file],
                expected_outputs=[output_file, property_file, gbw_file],
                deps=[],  # Self-contained subchain
                fingerprint=fingerprint if fingerprint else None,
                metadata={
                    "engine": "orca",
                    "subchain_basename": basename,
                    "chain_key": namespace_folder,
                    "public_types": public_types,
                    "moread_file": "scf.gbw" if target_idx > 0 else None,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)


class PySCFRecipe(BaseRecipe):
    """
    PySCF-Recipe: QC weak-chain/session model.

    Creates one job per subchain, executed as a Python subprocess.
    Similar to ORCA but uses internal execution rather than external binary.

    Working directory: calc/raw/scf_<suffix>/
    Artifacts: step_artifacts/<step_ulid>/results.json

    Used by: PySCF
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize subchain jobs for PySCF.

        For a chain [SCF, MP2], creates:
        - Job "s": SCF only
        - Job "s_m2": SCF + MP2 (session re-executes both)

        Args:
            steps: List of PySCF steps (first should be SCF)
            calc_raw_dir: Path to calc/raw/
            step_shas: Optional dict for fingerprinting

        Returns:
            JobGraph with subchain session jobs
        """
        if not steps:
            return JobGraph(jobs=[])

        registry = get_registry()
        
        # Verify topology before materialization
        verify_qc_topology(steps, registry)
        jobs: List[Job] = []

        # Get SCF root info for namespace folder
        scf_root = steps[0]
        scf_ulid = scf_root.meta.id
        namespace_folder = get_chain_namespace_folder(scf_ulid)
        working_dir = calc_raw_dir / namespace_folder

        # Build subchain for each step
        for target_idx, target_step in enumerate(steps):
            # Get public types for all steps in subchain
            subchain_steps = steps[: target_idx + 1]
            public_types = []

            for s in subchain_steps:
                spec = (
                    registry.get(str(s.step_type))
                    if s.step_type
                    else None
                )
                pt = spec.public_type if spec else "scf"
                public_types.append(pt)

            # Generate subchain basename from stable tokens
            try:
                basename = generate_subchain_basename(public_types)
            except ValueError:
                basename = "_".join(public_types)

            # Collect step IDs and SHAs for fingerprint
            step_ids = [s.meta.id for s in subchain_steps]
            step_sha_list = [
                self._get_step_sha(s, step_shas) or ""
                for s in subchain_steps
            ]
            fingerprint = compute_job_fingerprint(
                [sha for sha in step_sha_list if sha]
            )

            # Expected outputs: results.json for each step + checkpoint
            step_artifacts_dir = calc_raw_dir / "step_artifacts"
            expected_outputs = [
                step_artifacts_dir / s.meta.id / "results.json"
                for s in subchain_steps
            ]
            expected_outputs.append(working_dir / "checkpoint.chk")

            # Create job
            job = Job(
                id=basename,
                step_ids=step_ids,
                working_dir=working_dir,
                command=["<internal>"],  # Python subprocess
                input_files=[],  # Job spec passed via chain spec
                expected_outputs=expected_outputs,
                deps=[],  # Self-contained session
                fingerprint=fingerprint if fingerprint else None,
                metadata={
                    "engine": "pyscf",
                    "subchain_basename": basename,
                    "chain_key": namespace_folder,
                    "public_types": public_types,
                    "target_step_ulid": target_step.meta.id,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)


def get_recipe_for_engine(engine_family: str) -> BaseRecipe:
    """
    Get the appropriate recipe for an engine family.

    Args:
        engine_family: Engine family name ("qe", "orca", "pyscf")

    Returns:
        Recipe instance for the engine family

    Raises:
        ValueError: If engine family is unknown
    """
    recipes = {
        "qe": QERecipe,
        "orca": ORCARecipe,
        "pyscf": PySCFRecipe,
        "vasp": VASPRecipe,
    }

    recipe_class = recipes.get(engine_family)
    if recipe_class is None:
        raise ValueError(
            f"Unknown engine family '{engine_family}'. "
            f"Supported: {list(recipes.keys())}"
        )

    return recipe_class()
