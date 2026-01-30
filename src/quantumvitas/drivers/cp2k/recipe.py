"""CP2K recipe for input staging.

This module handles the preparation of CP2K input files.
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


class CP2KRecipe(BaseRecipe):
    """
    CP2K-Recipe: Isolated workdir per step, directory-state model.

    Creates one job per step. Each step runs in:
    `calc/raw/<step_ulid>/`  (Runtime SSOT)

    NO workdir cleanup (accumulates artifacts).

    File layout:
    - Input: input.inp
    - Output: output.log, cp2k_calc-* artifacts
    """

    def get_preflight_requirements(self, step) -> List["PreflightRequirement"]:
        """
        Get preflight requirements based on step parameters.

        CP2K declares requirements based on restart_policy.
        """
        from quantumvitas.execution.preflight import PreflightRequirement

        reqs = []
        params = getattr(step, "parameters", None) or {}
        restart_policy = params.get("restart_policy", {})

        if restart_policy.get("use_restart"):
            reqs.append(PreflightRequirement(
                artifact_type="restart",
                pattern="cp2k_calc-*.restart",
                source_step="predecessor",
                required=True,
                message="Restart file required but not found in {source_dir}",
            ))

        if restart_policy.get("use_wfn_guess"):
            reqs.append(PreflightRequirement(
                artifact_type="wfn",
                pattern="cp2k_calc-RESTART.wfn",
                source_step="predecessor",
                required=True,
                message="WFN file required but not found in {source_dir}",
            ))

        return reqs

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """Materialize jobs for CP2K steps."""
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

            # CP2K command
            command = ["cp2k.ssmp", "-i", "input.inp", "-o", "output.log"]

            input_files = [working_dir / "input.inp"]
            expected_outputs = [working_dir / "output.log"]

            # Add trajectory and cell for relax/md
            if gen_type in ("relax", "md"):
                expected_outputs.append(working_dir / "cp2k_calc-pos-1.xyz")
                expected_outputs.append(working_dir / "cp2k_calc-1.cell")  # NEW

            step_sha = self._get_step_sha(step, step_shas)

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
                fingerprint=step_sha,
                metadata={
                    "engine": "cp2k",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)

