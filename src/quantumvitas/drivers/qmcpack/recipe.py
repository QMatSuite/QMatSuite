"""QMCPACK recipe for input staging.

This module handles the preparation of QMCPACK input files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from quantumvitas.execution.recipes import BaseRecipe
from quantumvitas.execution.job_graph import Job, JobGraph
from quantumvitas.workflow.registry import get_registry

if TYPE_CHECKING:
    from quantumvitas.calculation.step import Step

logger = logging.getLogger(__name__)


class QMCPACKRecipe(BaseRecipe):
    """
    QMCPACK-Recipe: Isolated workdir per step, QMC model.

    Creates one job per step. Each step runs in its own isolated workdir:
    `calc/raw/<step_ulid>/`

    File layout:
    - Input: qmc_input.xml, *.h5 (wavefunction), *.xml (pseudopotentials)
    - Output: *.scalar.dat, *.dmc.dat, *.opt.xml

    Used by: QMCPACK
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize jobs for QMCPACK steps.

        Each step gets its own isolated workdir: calc_raw_dir / step_ulid

        Args:
            steps: List of QMCPACK steps
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
            step_type = step.step_type_spec
            spec = registry.get(step_type) if step_type else None
            gen_type = spec.step_type_gen if spec else "unknown"

            job_id = step.meta.ulid
            working_dir = calc_raw_dir / step.meta.ulid
            executable = spec.executable if spec else "qmcpack"

            command = [executable, "qmc_input.xml"]

            input_files = [
                working_dir / "qmc_input.xml",
            ]

            # Expected outputs depend on step type
            expected_outputs = []
            if gen_type == "dmc":
                expected_outputs.append(working_dir / "qmc.s001.scalar.dat")
            else:
                expected_outputs.append(working_dir / "qmc.s000.scalar.dat")

            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None

            deps = []
            if len(jobs) > 0:
                deps = [jobs[-1].id]

            job = Job(
                id=job_id,
                step_ulids=[step.meta.ulid],
                working_dir=working_dir,
                command=command,
                input_files=input_files,
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=fingerprint,
                metadata={
                    "engine": "qmcpack",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
