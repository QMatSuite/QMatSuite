"""Siesta Recipe: Directory-state, isolated workdir model.

Each Siesta step gets its own working directory. Pseudopotential
files are staged into the workdir. Restart via .DM file copying.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from quantumvitas.execution.job_graph import Job, JobGraph
from quantumvitas.execution.recipes import BaseRecipe
from quantumvitas.workflow.registry import get_registry

if TYPE_CHECKING:
    from quantumvitas.calculation.step import Step


class SiestaRecipe(BaseRecipe):
    """
    Siesta Recipe: Directory-state with ISOLATED workdir.

    Creates one job per step. Each job gets its own subdirectory
    under calc/raw/{step_ulid}/. Pseudopotential files and optional
    .DM restart files are staged into the workdir.

    Working directory: calc/raw/{step_ulid}/
    Input files: {system_label}.fdf
    Output files: {system_label}.out, .EIG, .FA, .DM, FORCE_STRESS, etc.
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize one job per Siesta step with isolated workdirs.

        Args:
            steps: List of Siesta steps
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
            spec = registry.get(str(step_type)) if step_type else None

            if spec:
                gen_type = spec.step_type_gen
            else:
                gen_type = str(step_type) if step_type else "scf"

            # ISOLATED: each step gets its own subdirectory
            step_ulid = step.meta.ulid
            working_dir = calc_raw_dir / step_ulid

            # System label for Siesta file naming
            system_label = gen_type

            # Input: FDF file
            fdf_name = f"{system_label}.fdf"

            # Command: siesta reads from stdin
            command = ["siesta"]

            # Expected outputs
            expected_outputs = [
                working_dir / f"{system_label}.out",
                working_dir / f"{system_label}.EIG",
                working_dir / "FORCE_STRESS",
                working_dir / "0_NORMAL_EXIT",
            ]
            if gen_type in ("relax", "md"):
                expected_outputs.append(working_dir / f"{system_label}.MDE")

            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None

            # Dependencies: later steps depend on earlier ones (for .DM staging)
            deps = [f"step_{idx - 1:02d}"] if idx > 0 else []

            job = Job(
                id=job_id,
                step_ulids=[step_ulid],
                working_dir=working_dir,
                command=command,
                input_files=[working_dir / fdf_name],
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=fingerprint,
                metadata={
                    "engine": "siesta",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                    "system_label": system_label,
                    "fdf_name": fdf_name,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
