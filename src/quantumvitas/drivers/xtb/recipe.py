"""xTB Recipe: Directory-state, isolated workdir model.

The simplest possible recipe. Each step gets its own working directory.
No pseudopotentials, no restart staging, no shared state.
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


class XTBRecipe(BaseRecipe):
    """
    xTB Recipe: Directory-state with ISOLATED workdir.

    Creates one job per step. Each job gets its own subdirectory
    under calc/raw/{step_ulid}/. No pseudopotential staging needed.

    Working directory: calc/raw/{step_ulid}/
    Input files: input.xyz
    Output files: xtbopt.xyz, xtb.out, charges, wbo, .xtboptok
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize one job per xTB step with isolated workdirs.

        Args:
            steps: List of xTB steps
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
            # Convert SPEC (e.g., "xtb_relax") to GEN (e.g., "relax")
            # before registry lookup, since registry.get() expects GEN types
            step_type_str = str(step_type) if step_type else None
            gen_key = gen_from(step_type_str) if step_type_str else None
            spec = registry.get_for_engine(gen_key, "xtb") if gen_key else None

            if spec:
                gen_type = spec.step_type_gen
            else:
                gen_type = str(step_type) if step_type else "relax"

            # ISOLATED: each step gets its own subdirectory
            step_ulid = step.meta.ulid
            working_dir = calc_raw_dir / step_ulid

            # Build command from step parameters
            from .writer import build_xtb_command

            params: dict = {}
            if hasattr(step, "params") and step.params:
                params = dict(step.params)

            executable = "xtb"
            try:
                from quantumvitas.core.engines.engine_registry import resolve_active_binary

                resolved = resolve_active_binary("xtb", binary_name="xtb")
                if resolved and resolved.is_file():
                    executable = str(resolved)
            except Exception:
                pass

            _runtype_map = {"relax": "opt", "md": "md", "grad": "grad", "hess": "hess"}
            cmd = build_xtb_command(
                executable=executable,
                runtype=_runtype_map.get(gen_type, "sp"),
                gfn_level=params.get("gfn_level", 2),
                opt_level=params.get("opt_level"),
                charge=params.get("charge", 0),
                uhf=params.get("uhf", 0),
                solvent=params.get("solvent"),
                solvent_model=params.get("solvent_model", "alpb"),
                accuracy=params.get("accuracy"),
                max_iterations=params.get("max_iterations"),
            )

            # Expected outputs
            expected_outputs = [working_dir / "xtb.out"]
            if gen_type == "relax":
                expected_outputs.append(working_dir / "xtbopt.xyz")

            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None

            job = Job(
                id=job_id,
                step_ulids=[step_ulid],
                working_dir=working_dir,
                command=cmd,
                input_files=[working_dir / "input.xyz"],
                expected_outputs=expected_outputs,
                deps=[],
                fingerprint=fingerprint,
                metadata={
                    "engine": "xtb",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
