"""QE Recipe: Directory-state, step-run model."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from qmatsuite.execution.job_graph import Job, JobGraph
from qmatsuite.execution.recipes import BaseRecipe
from qmatsuite.workflow.registry import get_registry

if TYPE_CHECKING:
    from qmatsuite.calculation.step import Step


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
            spec = None
            if step_type:
                # Registry.get() takes step_type_gen, not spec.
                # First try gen_from() to extract gen from spec.
                from qmatsuite.workflow.step_type_convert import gen_from
                try:
                    gen = gen_from(str(step_type))
                    spec = registry.get(gen)
                except Exception:
                    spec = registry.get(str(step_type))

            # Determine executable and input file
            if spec:
                executable = spec.executable
                gen_type = spec.step_type_gen
            else:
                executable = "pw.x"
                gen_type = str(step_type) if step_type else "custom"

            # Input file uses GEN naming (per Constitution §F)
            input_file = f"{gen_type}.in"

            # Build command
            command = [executable, input_file]

            # Expected outputs (GEN naming)
            expected_outputs = [calc_raw_dir / f"{gen_type}.out"]

            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None

            # Create job
            job = Job(
                id=job_id,
                step_ulids=[step.meta.ulid],
                working_dir=calc_raw_dir,
                command=command,
                input_files=[calc_raw_dir / input_file],
                expected_outputs=expected_outputs,
                deps=[],  # Conservative: no explicit deps, use prefix selection
                fingerprint=fingerprint,
                metadata={
                    # W90 companion steps (wannierprep, wannier) use QE binaries
                # (wannier90.x from QE's external/) and are run by the QE
                # handler.  Route them to "qe" so the executor dispatches
                # correctly instead of sending them to the standalone W90
                # handler which expects prebaked .amn/.mmn/.eig.
                "engine": "qe" if gen_type in ("wannierprep", "wannier", "pw2wannier") else (spec.engine if spec else "qe"),
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                    "scratch_dir": calc_raw_dir / "outdir",
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)

