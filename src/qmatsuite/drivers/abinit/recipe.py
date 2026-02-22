"""ABINIT Recipe: Directory-state archetype with SHARED WorkdirPolicy.

All steps execute in calc/raw/. Sequential chaining via file dependencies:
- SCF produces: {prefix}o_DEN, {prefix}o_WFK
- NSCF reads: getden pointing to SCF density
- Relax produces: {prefix}o_HIST.nc, final structure

This follows the QE-like Directory-state pattern where outputs are shared.
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


class AbinitRecipe(BaseRecipe):
    """
    ABINIT Recipe: SHARED workdir model (Directory-state archetype).

    Creates one job per step, all executing in calc/raw/:
    - scf: basic SCF calculation
    - nscf: non-self-consistent (reads density from prior SCF)
    - relax: ionic/cell relaxation

    File naming: step_XX.abi (input), step_XX.abo (output)
    Dependencies: NSCF depends on prior SCF for density files.
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        registry = get_registry()
        jobs: List[Job] = []
        scf_job_id: Optional[str] = None

        for idx, step in enumerate(steps):
            job_id = f"step_{idx:02d}"
            step_prefix = f"step_{idx:02d}"
            step_type = step.step_type_spec
            step_type_str = str(step_type) if step_type else None
            gen_key = gen_from(step_type_str) if step_type_str else None
            spec = registry.get_for_engine(gen_key, "abinit") if gen_key else None

            if spec:
                gen_type = spec.step_type_gen
            else:
                gen_type = gen_key or "scf"

            step_ulid = step.meta.ulid

            # All steps use shared calc/raw/ directory
            working_dir = calc_raw_dir

            # Input and output files
            input_file = f"{step_prefix}.abi"
            output_file = f"{step_prefix}.abo"

            # Build command
            command = ["abinit", input_file]

            # Expected outputs depend on step type
            expected_outputs: List[Path] = [working_dir / output_file]
            if gen_type == "scf":
                # SCF produces density and wavefunctions
                expected_outputs.extend([
                    working_dir / f"{step_prefix}o_DEN",
                    working_dir / f"{step_prefix}o_WFK",
                ])
                scf_job_id = job_id
            elif gen_type == "nscf":
                # NSCF produces eigenvalues
                expected_outputs.append(working_dir / f"{step_prefix}o_EIG")
            elif gen_type == "relax":
                # Relax produces history file
                expected_outputs.append(working_dir / f"{step_prefix}o_HIST.nc")

            # Dependencies: NSCF typically depends on SCF
            deps: list[str] = []
            if gen_type == "nscf" and scf_job_id is not None:
                deps = [scf_job_id]

            step_sha = self._get_step_sha(step, step_shas)

            job = Job(
                id=job_id,
                step_ulids=[step_ulid],
                working_dir=working_dir,
                command=command,
                input_files=[working_dir / input_file],
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=step_sha if step_sha else None,
                metadata={
                    "engine": "abinit",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                    "step_prefix": step_prefix,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
