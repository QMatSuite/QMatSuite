"""MACE Recipe: Directory-state, isolated workdir model.

Simple recipe: each step gets its own working directory.
No pseudopotentials, no restart staging, no shared state.
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


class MACERecipe(BaseRecipe):
    """MACE Recipe: Directory-state with ISOLATED workdir.

    Creates one job per step. Each job gets its own subdirectory
    under calc/raw/{step_ulid}/. No external resource staging needed
    (MACE models auto-download from HuggingFace/GitHub).

    Working directory: calc/raw/{step_ulid}/
    Input files: {gen_type}.py, structure.json
    Output files: results.json, trajectory.jsonl, final_structure.json
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """Materialize one job per MACE step with isolated workdirs."""
        registry = get_registry()
        jobs: List[Job] = []

        for idx, step in enumerate(steps):
            job_id = f"step_{idx:02d}"

            step_type = step.step_type_spec
            step_type_str = str(step_type) if step_type else None
            gen_key = gen_from(step_type_str) if step_type_str else None
            spec = registry.get_for_engine(gen_key, "mace") if gen_key else None

            if spec:
                gen_type = spec.step_type_gen
            else:
                gen_type = str(step_type) if step_type else "scf"

            # ISOLATED: each step gets its own subdirectory
            step_ulid = step.meta.ulid
            working_dir = calc_raw_dir / step_ulid

            # Command: python {gen_type}.py
            script_name = f"{gen_type}.py"
            python_exe = "python"
            try:
                from qmatsuite.core.engines.engine_registry import resolve_active_python
                resolved = resolve_active_python("mace")
                if resolved and resolved.is_file():
                    python_exe = str(resolved)
            except Exception:
                pass

            cmd = [python_exe, script_name]

            # Expected outputs
            expected_outputs = [working_dir / "results.json"]
            if gen_type in ("relax", "md"):
                expected_outputs.append(working_dir / "trajectory.jsonl")

            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None

            job = Job(
                id=job_id,
                step_ulids=[step_ulid],
                working_dir=working_dir,
                command=cmd,
                input_files=[
                    working_dir / script_name,
                    working_dir / "structure.json",
                ],
                expected_outputs=expected_outputs,
                deps=[],
                fingerprint=fingerprint,
                metadata={
                    "engine": "mace",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
