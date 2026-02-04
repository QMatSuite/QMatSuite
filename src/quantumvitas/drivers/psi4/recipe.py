"""Psi4 recipe for input staging.

This module handles the preparation of Psi4 calculation chains.
Follows the strong-chain pattern (like PySCF/ORCA).
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


class Psi4Recipe(BaseRecipe):
    """
    Psi4-Recipe: QC strong-chain model.

    Creates one job per subchain, executed as a Python subprocess.
    For a chain [SCF, MP2], creates:
    - Job "s": SCF only
    - Job "s_m2": SCF + MP2 (session re-executes both)

    Working directory: calc/raw/scf_<suffix>/
    Artifacts: step_artifacts/<step_ulid>/results.json
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """Materialize subchain jobs for Psi4."""
        if not steps:
            return JobGraph(jobs=[])

        registry = get_registry()

        # Verify topology before materialization
        verify_qc_topology(steps, registry)
        jobs: List[Job] = []

        # Get SCF root info for namespace folder
        scf_root = steps[0]
        scf_ulid = scf_root.meta.ulid
        namespace_folder = get_chain_namespace_folder(scf_ulid)
        working_dir = calc_raw_dir / namespace_folder

        # Build subchain for each step
        for target_idx, target_step in enumerate(steps):
            subchain_steps = steps[: target_idx + 1]
            gen_types = []

            for s in subchain_steps:
                spec = (
                    registry.get(str(s.step_type_spec))
                    if s.step_type_spec
                    else None
                )
                gt = spec.step_type_gen if spec else "scf"
                gen_types.append(gt)

            try:
                basename = generate_subchain_basename(gen_types)
            except ValueError:
                basename = "_".join(gen_types)

            step_ulids = [s.meta.ulid for s in subchain_steps]
            step_sha_list = [
                self._get_step_sha(s, step_shas) or ""
                for s in subchain_steps
            ]
            fingerprint = compute_job_fingerprint(
                [sha for sha in step_sha_list if sha]
            )

            step_artifacts_dir = calc_raw_dir / "step_artifacts"
            expected_outputs = [
                step_artifacts_dir / s.meta.ulid / "results.json"
                for s in subchain_steps
            ]
            expected_outputs.append(working_dir / "wavefunction.npy")

            job = Job(
                id=basename,
                step_ulids=step_ulids,
                working_dir=working_dir,
                command=["<internal>"],
                input_files=[],
                expected_outputs=expected_outputs,
                deps=[],
                fingerprint=fingerprint if fingerprint else None,
                metadata={
                    "engine": "psi4",
                    "subchain_basename": basename,
                    "chain_key": namespace_folder,
                    "gen_types": gen_types,
                    "target_step_ulid": target_step.meta.ulid,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
