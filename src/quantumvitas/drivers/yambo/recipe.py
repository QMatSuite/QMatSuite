"""Yambo Recipe: ISOLATED workdir with shared SAVE symlink.

Each step gets its own subdirectory under calc/raw/{step_ulid}/.
The setup step creates SAVE/ in calc/raw/SAVE/. Subsequent steps
(gw, bse, optics) symlink SAVE/ into their working directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from quantumvitas.execution.job_graph import Job, JobGraph
from quantumvitas.execution.recipes import BaseRecipe
from quantumvitas.workflow.registry import get_registry
from quantumvitas.workflow.step_type_convert import gen_from

if TYPE_CHECKING:
    from quantumvitas.calculation.step import Step


class YamboRecipe(BaseRecipe):
    """
    Yambo Recipe: ISOLATED workdir model.

    Creates one job per step:
    - setup: runs p2y + yambo init, creates SAVE/ in calc/raw/SAVE/
    - gw/bse/optics: each gets calc/raw/{step_ulid}/ with SAVE symlink

    Dependencies: gw/bse/optics jobs depend on setup job.
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        registry = get_registry()
        jobs: List[Job] = []
        setup_job_id: Optional[str] = None

        for idx, step in enumerate(steps):
            job_id = f"step_{idx:02d}"
            step_type = step.step_type_spec
            step_type_str = str(step_type) if step_type else None
            gen_key = gen_from(step_type_str) if step_type_str else None
            spec = registry.get_for_engine(gen_key, "yambo") if gen_key else None

            if spec:
                gen_type = spec.step_type_gen
            else:
                gen_type = gen_key or "optics"

            step_ulid = step.meta.ulid
            working_dir = calc_raw_dir / step_ulid

            # Build command based on gen type
            if gen_type == "setup":
                # Handler runs p2y + yambo init internally
                command = ["yambo"]
                expected_outputs = [calc_raw_dir / "SAVE" / "ns.db1"]
                setup_job_id = job_id
            else:
                # GW/BSE/optics: yambo -F <input> -J <jobname> -C <output>
                jobname = f"{gen_type}_run"
                input_file = f"{gen_type}.in"
                output_dir = f"{gen_type}_output"
                command = [
                    "yambo", "-F", input_file,
                    "-J", jobname, "-C", output_dir,
                ]
                expected_outputs = [working_dir / output_dir]

            # Dependencies: calculation steps depend on setup
            deps: list[str] = []
            if gen_type != "setup" and setup_job_id is not None:
                deps = [setup_job_id]

            step_sha = self._get_step_sha(step, step_shas)

            job = Job(
                id=job_id,
                step_ulids=[step_ulid],
                working_dir=working_dir,
                command=command,
                input_files=[],
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=step_sha if step_sha else None,
                metadata={
                    "engine": "yambo",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
