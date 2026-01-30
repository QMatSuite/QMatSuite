"""LAMMPS recipe for input staging.

This module handles the preparation of LAMMPS input files.
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


class LAMMPSRecipe(BaseRecipe):
    """
    LAMMPS-Recipe: Isolated workdir per step, classical MD model.
    
    Creates one job per step. Each step runs in its own isolated workdir:
    `calc/raw/<step_ulid>/`
    
    File layout:
    - Input: in.lammps, structure.data, *.eam/*.tersoff (potentials)
    - Output: log.lammps, *.lammpstrj, final.data (for relax)
    
    Used by: LAMMPS
    """
    
    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize jobs for LAMMPS steps.
        
        Each step gets its own isolated workdir: calc_raw_dir / step_ulid
        
        Args:
            steps: List of LAMMPS steps
            calc_raw_dir: Path to calc/raw/
            step_shas: Optional dict for fingerprinting
        
        Returns:
            JobGraph with one job per step
        """
        if not steps:
            return JobGraph(jobs=[])
        
        registry = get_registry()
        jobs: List[Job] = []
        
        for step in steps:
            # Get step type info
            step_type = step.step_type_spec
            spec = registry.get(step_type) if step_type else None
            gen_type = spec.step_type_gen if spec else "unknown"

            # Job ID = step ULID
            job_id = step.meta.ulid

            # Working directory: isolated per step
            working_dir = calc_raw_dir / step.meta.ulid

            # LAMMPS executable (placeholder; actual path resolved by LammpsEngine at runtime)
            executable = spec.executable if spec else "lmp"

            # Command: lmp -in in.lammps -log log.lammps
            command = [executable, "-in", "in.lammps", "-log", "log.lammps"]

            # Input files (will be materialized into working_dir by LammpsEngine)
            input_files = [
                working_dir / "in.lammps",
                working_dir / "structure.data",
            ]

            # Expected outputs
            expected_outputs = [
                working_dir / "log.lammps",
            ]
            # Add final.data for relax steps
            if gen_type == "relax":
                expected_outputs.append(working_dir / "final.data")
            
            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None
            
            # Dependencies: include restart_from if present
            deps = []
            
            # Linear dependency on previous job (conservative)
            if len(jobs) > 0:
                deps = [jobs[-1].id]
            
            # Explicit restart_from dependency (artifact-based)
            # This ensures downstream step waits for upstream artifact
            step_params = getattr(step, "parameters", None) or getattr(step, "options", {})
            if not step_params:
                # Try to load from step spec (best-effort)
                try:
                    from quantumvitas.calculation.structure_steps import StructureStepSpec
                    from quantumvitas.core.resolution import require_step
                    from quantumvitas.core.project_utils import load_project_config
                    # Note: We don't have project_root here, so this may not work
                    # This is a best-effort enhancement
                    pass
                except Exception:
                    pass
            
            restart_from = step_params.get("restart_from") if isinstance(step_params, dict) else None
            if restart_from:
                # Find the job that contains the restart_from step
                for existing_job in jobs:
                    if restart_from in existing_job.step_ids:
                        if existing_job.id not in deps:
                            deps.append(existing_job.id)
                        break
                else:
                    # restart_from references a step not yet in jobs list
                    # This is unusual but could happen with non-linear topologies
                    # Log for debugging
                    logging.getLogger(__name__).warning(
                        f"restart_from={restart_from} references step not in current jobs"
                    )
            
            # Create job
            job = Job(
                id=job_id,
                step_ids=[step.meta.ulid],
                working_dir=working_dir,
                command=command,
                input_files=input_files,
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=fingerprint,
                metadata={
                    "engine": "lammps",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                },
            )
            jobs.append(job)
        
        return JobGraph(jobs=jobs)

