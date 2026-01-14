"""
JobGraph: Runtime-only job execution model.

This module defines the Job and JobGraph abstractions used for
execution planning across all engine types.

Per engine_recipes_jobgraph_plan.md (Constitution):
- JobGraph is runtime-only (NOT persisted, derived each run)
- Manifest remains the ONLY persisted run tracking truth
- Jobs reference steps by ULID, not by GEN/SPEC step types
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class SelectionMode(str, Enum):
    """How to select which jobs to execute."""

    ALL = "all"  # Run all jobs (Run Calc mode)
    TARGET = "target"  # Run jobs up to and including target (Run Step mode)


@dataclass
class Job:
    """
    A Job represents a single unit of execution.

    For QE-Recipe: Job = one executable invocation (one step)
    For ORCA-Recipe: Job = one subchain execution (SCF root → target step)
    For PySCF-Recipe: Job = one chain_session execution (SCF root → target step)

    Attributes:
        id: Unique job identifier within the graph.
            - QE: "step_00", "step_01", etc.
            - ORCA/PySCF: Stable token path like "s", "s_t", "s_m2"

        step_ids: List of step ULIDs covered by this job.
            - QE: Single step [step_ulid]
            - ORCA/PySCF: Chain from SCF root [scf_ulid, ..., target_ulid]

        working_dir: Directory where this job executes.
            - QE: calc/raw/
            - ORCA/PySCF: calc/raw/scf_<suffix>/

        command: Command to execute.
            - QE: ["pw.x", "scf.in"]
            - ORCA: ["orca", "s_t.inp"]
            - PySCF: ["<internal>"] (Python subprocess)

        input_files: Input files this job reads (for reference).

        expected_outputs: Output files to check for completion.
            - QE: [scf.out]
            - ORCA: [s_t.out, s_t.property.txt, scf.gbw]
            - PySCF: [results.json, checkpoint.chk]

        deps: Job IDs this job depends on.
            - QE: Conservative deps for prefix-to-target
            - ORCA/PySCF: No inter-job deps (self-contained subchains)

        fingerprint: Combined SHA for incremental skip logic.
            Computed from step SHAs; used with manifest for skip decisions.

        metadata: Engine-specific data.
            - engine: Engine name ("qe", "orca", "pyscf")
            - spec_step_type: SPEC step type for dispatch
            - scratch_dir: Engine scratch directory if applicable
    """

    id: str
    step_ids: List[str]
    working_dir: Path
    command: List[str]
    input_files: List[Path] = field(default_factory=list)
    expected_outputs: List[Path] = field(default_factory=list)
    deps: List[str] = field(default_factory=list)
    fingerprint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def engine(self) -> Optional[str]:
        """Get engine name from metadata."""
        return self.metadata.get("engine")

    @property
    def spec_step_type(self) -> Optional[str]:
        """Get SPEC step type from metadata (for single-step jobs)."""
        return self.metadata.get("spec_step_type")

    @property
    def is_internal(self) -> bool:
        """Check if this is an internal Python job (PySCF)."""
        return self.command == ["<internal>"]


@dataclass
class JobGraph:
    """
    Runtime-only DAG of jobs for a calculation.

    JobGraph is materialized from calculation steps + engine recipe.
    NOT persisted. Derived each run.

    The jobs list is topologically sorted (execution order).
    """

    jobs: List[Job]

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def get_job_by_step_id(self, step_id: str) -> Optional[Job]:
        """Get the job that contains a given step ID."""
        for job in self.jobs:
            if step_id in job.step_ids:
                return job
        return None

    def get_jobs_for_target(
        self, target_step_id: str, mode: SelectionMode = SelectionMode.TARGET
    ) -> List[Job]:
        """
        Get jobs to execute for a target step.

        For TARGET mode (Run Step):
        - Returns all jobs from start up to and including the job
          that contains the target step.
        - This is conservative prefix-to-target selection.

        For ALL mode (Run Calc):
        - Returns all jobs.

        Args:
            target_step_id: ULID of the target step
            mode: Selection mode (ALL or TARGET)

        Returns:
            List of jobs to execute in order.
        """
        if mode == SelectionMode.ALL:
            return list(self.jobs)

        # Find job containing target step
        target_job = self.get_job_by_step_id(target_step_id)
        if target_job is None:
            return []

        # Return prefix up to and including target job
        result = []
        for job in self.jobs:
            result.append(job)
            if job.id == target_job.id:
                break

        return result

    def get_dependencies(self, job_id: str) -> List[Job]:
        """Get all jobs that a given job depends on."""
        job = self.get_job(job_id)
        if job is None:
            return []

        return [self.get_job(dep_id) for dep_id in job.deps if self.get_job(dep_id)]

    def __len__(self) -> int:
        return len(self.jobs)

    def __iter__(self):
        return iter(self.jobs)


def compute_job_fingerprint(step_shas: List[str]) -> str:
    """
    Compute a fingerprint for a job from its step SHAs.

    For single-step jobs (QE-Recipe), this is just the step SHA.
    For multi-step jobs (ORCA/PySCF-Recipe), this is a hash of all step SHAs.

    Args:
        step_shas: List of step SHA256 hashes

    Returns:
        Combined fingerprint as hex string
    """
    if not step_shas:
        return ""

    if len(step_shas) == 1:
        return step_shas[0]

    # Combine multiple SHAs
    combined = "|".join(sorted(step_shas))
    return hashlib.sha256(combined.encode()).hexdigest()
