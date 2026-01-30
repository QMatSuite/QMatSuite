"""VASP recipe for input staging.

This module handles the preparation of VASP input files.
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


class VASPRecipe(BaseRecipe):
    """
    VASP-Recipe: Directory-state, one job per step (isolated workdirs).
    
    Creates one job per step. Each step runs in its own isolated workdir:
    `calc/raw/<step_ulid>/`
    
    Working directory is completely cleaned before execution (rm -rf).
    Artifacts (CHGCAR/WAVECAR) are copied from reference SCF step.
    
    Used by: VASP
    """
    
    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        Materialize jobs for VASP steps.
        
        Each step gets its own isolated workdir: calc_raw_dir / step_ulid
        
        Args:
            steps: List of VASP steps
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
            
            # VASP executable (from spec)
            executable = spec.executable if spec else "vasp_std"
            
            # Command: just the executable (VASP reads POSCAR/INCAR/KPOINTS/POTCAR from CWD)
            command = [executable]
            
            # Input files (will be materialized into working_dir)
            input_files = [
                working_dir / "POSCAR",
                working_dir / "INCAR",
                working_dir / "KPOINTS",
                working_dir / "POTCAR",
            ]
            
            # Expected outputs
            expected_outputs = [
                working_dir / "OUTCAR",
                working_dir / "OSZICAR",
            ]
            
            # Fingerprint
            step_sha = self._get_step_sha(step, step_shas)
            fingerprint = step_sha if step_sha else None
            
            # Dependencies: linear (each step depends on previous)
            deps = []
            if len(jobs) > 0:
                deps = [jobs[-1].id]
            
            # Create job
            job = Job(
                id=job_id,
                step_ulids=[step.meta.ulid],
                working_dir=working_dir,
                command=command,
                input_files=input_files,
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=fingerprint,
                metadata={
                    "engine": "vasp",
                    "step_type_spec": spec.step_type_spec if spec else None,
                    "step_type_gen": gen_type,
                },
            )
            jobs.append(job)
        
        return JobGraph(jobs=jobs)

