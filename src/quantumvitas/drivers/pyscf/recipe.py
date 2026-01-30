"""PySCF recipe for input staging.

This module handles the preparation of PySCF calculation scripts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from quantumvitas.execution.recipes import BaseRecipe
from quantumvitas.execution.job_graph import Job, JobGraph, compute_job_fingerprint
from quantumvitas.workflow.registry import (
    get_registry,
    generate_subchain_basename,
    get_chain_namespace_folder,
)
from quantumvitas.execution.recipes import verify_qc_topology

if TYPE_CHECKING:
    from quantumvitas.calculation.step import Step

logger = logging.getLogger(__name__)


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
                pt = spec.step_type_gen if spec else "scf"
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

