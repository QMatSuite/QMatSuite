"""GPAW Recipe: Directory-state, step-run model.

GPAW uses a shared working directory where steps chain through .gpw
restart files, analogous to QE's outdir mechanism.
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


class GPAWRecipe(BaseRecipe):
    """
    GPAW-Recipe: Directory-state, step-run model.

    Creates one job per step. Jobs share the same working directory.
    Steps chain via .gpw restart files written to the shared directory.

    Working directory: calc/raw/
    Input files: {gen_type}.py (generated Python scripts)
    Output files: results.json, {gen_type}.txt, {gen_type}.gpw
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize one job per GPAW step.

        Args:
            steps: List of GPAW steps
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
            # Convert SPEC (e.g., "gpaw_scf") to GEN (e.g., "scf")
            # before registry lookup, since registry.get() expects GEN types
            step_type_str = str(step_type) if step_type else None
            gen_key = gen_from(step_type_str) if step_type_str else None
            spec = registry.get_for_engine(gen_key, "gpaw") if gen_key else None

            if spec:
                gen_type = spec.step_type_gen
            else:
                gen_type = gen_key if gen_key else "scf"

            # Input: generated Python script
            script_name = f"{gen_type}.py"

            # Command: python script.py
            command = ["python", script_name]

            # Expected outputs
            expected_outputs = [
                calc_raw_dir / "results.json",
                calc_raw_dir / f"{gen_type}.txt",
            ]
            if gen_type in ("scf", "nscf", "relax", "md"):
                expected_outputs.append(calc_raw_dir / f"{gen_type}.gpw")
            if gen_type == "bandspw":
                expected_outputs.append(calc_raw_dir / "bandstructure.json")
            if gen_type == "dos":
                expected_outputs.append(calc_raw_dir / "dos.json")

            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None

            job = Job(
                id=job_id,
                step_ulids=[step.meta.ulid],
                working_dir=calc_raw_dir,
                command=command,
                input_files=[calc_raw_dir / script_name],
                expected_outputs=expected_outputs,
                deps=[],
                fingerprint=fingerprint,
                metadata={
                    "engine": "gpaw",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                    "script_name": script_name,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
