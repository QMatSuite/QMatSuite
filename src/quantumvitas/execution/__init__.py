"""
Execution module for runtime job management.

This module provides:
- Job: A single unit of execution (one engine invocation)
- JobGraph: Runtime-only DAG of jobs for a calculation
- Recipe implementations: QE, ORCA, PySCF materialization strategies

Per engine_recipes_jobgraph_plan.md (Constitution §E):
- JobGraph is runtime-only (NOT persisted, derived each run)
- Manifest remains the ONLY persisted run tracking truth
"""

from quantumvitas.execution.job_graph import (
    Job,
    JobGraph,
    SelectionMode,
    compute_job_fingerprint,
)

__all__ = [
    "Job",
    "JobGraph",
    "SelectionMode",
    "compute_job_fingerprint",
]
