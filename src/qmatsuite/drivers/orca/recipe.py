"""ORCA recipe for input staging.

This module handles the preparation of ORCA input files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from qmatsuite.execution.recipes import BaseRecipe
from qmatsuite.execution.job_graph import Job, JobGraph, compute_job_fingerprint
from qmatsuite.workflow.registry import (
    get_registry,
    generate_subchain_basename,
    get_chain_namespace_folder,
)
from qmatsuite.execution.recipes import verify_qc_topology

if TYPE_CHECKING:
    from qmatsuite.calculation.step import Step

logger = logging.getLogger(__name__)


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
        scf_ulid = scf_root.meta.ulid
        namespace_folder = get_chain_namespace_folder(scf_ulid)
        working_dir = calc_raw_dir / namespace_folder

        # Build subchain for each step
        for target_idx, target_step in enumerate(steps):
            # Get gen types for all steps in subchain
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

            # Generate subchain basename from stable tokens
            try:
                basename = generate_subchain_basename(gen_types)
            except ValueError:
                # Fallback if token not defined
                basename = "_".join(gen_types)

            # Collect step IDs and SHAs for fingerprint
            step_ulids = [s.meta.ulid for s in subchain_steps]
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
                step_ulids=step_ulids,
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
                    "gen_types": gen_types,
                    "moread_file": "scf.gbw" if target_idx > 0 else None,
                },
            )
            jobs.append(job)
        
        return JobGraph(jobs=jobs)

