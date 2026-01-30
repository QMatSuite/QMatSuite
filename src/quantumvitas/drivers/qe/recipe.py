"""QE Recipe: Directory-state, step-run model."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from quantumvitas.execution.job_graph import Job, JobGraph
from quantumvitas.execution.recipes import BaseRecipe
from quantumvitas.workflow.registry import get_registry

if TYPE_CHECKING:
    from quantumvitas.calculation.step import Step


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
            step_type = step.step_type_spec
            spec = registry.get(str(step_type)) if step_type else None

            # Determine executable and input file
            if spec:
                executable = spec.executable
                public_type = spec.step_type_gen
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
                step_ids=[step.meta.ulid],
                working_dir=calc_raw_dir,
                command=command,
                input_files=[calc_raw_dir / input_file],
                expected_outputs=expected_outputs,
                deps=[],  # Conservative: no explicit deps, use prefix selection
                fingerprint=fingerprint,
                metadata={
                    "engine": "qe",
                    "spec_step_type": spec.step_type_spec if spec else None,
                    "step_type_gen": public_type,
                    "scratch_dir": calc_raw_dir / "outdir",
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)

