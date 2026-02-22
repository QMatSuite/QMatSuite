"""Gaussian Recipe: Directory-state, isolated workdir model.

Each step gets its own working directory. No shared state between steps.
Similar to xTB recipe - the simplest possible model.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from qmatsuite.execution.job_graph import Job, JobGraph
from qmatsuite.execution.recipes import BaseRecipe
from qmatsuite.workflow.registry import get_registry
from qmatsuite.workflow.step_type_convert import gen_from

if TYPE_CHECKING:
    from qmatsuite.calculation.step import Step


class GaussianRecipe(BaseRecipe):
    """
    Gaussian Recipe: Directory-state with ISOLATED workdir.

    Creates one job per step. Each job gets its own subdirectory
    under calc/raw/{step_ulid}/.

    Working directory: calc/raw/{step_ulid}/
    Input files: input.gjf
    Output files: output.log, *.chk
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize one job per Gaussian step with isolated workdirs.

        Args:
            steps: List of Gaussian steps
            calc_raw_dir: Path to calc/raw/
            step_shas: Optional dict for fingerprinting

        Returns:
            JobGraph with one job per step
        """
        registry = get_registry()
        jobs: List[Job] = []

        for idx, step in enumerate(steps):
            job_id = f"step_{idx:02d}"

            step_type = step.step_type_spec
            # Convert SPEC (e.g., "gaussian_scf") to GEN (e.g., "scf")
            step_type_str = str(step_type) if step_type else None
            gen_key = gen_from(step_type_str) if step_type_str else None
            spec = registry.get_for_engine(gen_key, "gaussian") if gen_key else None

            if spec:
                gen_type = spec.step_type_gen
            else:
                gen_type = gen_key if gen_key else "scf"

            # ISOLATED: each step gets its own subdirectory
            step_ulid = step.meta.ulid
            working_dir = calc_raw_dir / step_ulid

            # Command: Gaussian reads from stdin
            # Handler will execute: g09 < input.gjf > output.log
            cmd = ["g09"]

            # Expected outputs
            expected_outputs = [working_dir / "output.log"]

            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None

            job = Job(
                id=job_id,
                step_ulids=[step_ulid],
                working_dir=working_dir,
                command=cmd,
                input_files=[working_dir / "input.gjf"],
                expected_outputs=expected_outputs,
                deps=[],
                fingerprint=fingerprint,
                metadata={
                    "engine": "gaussian",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
