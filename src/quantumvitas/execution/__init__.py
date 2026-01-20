"""
Execution module for runtime job management.

This module provides:
- Job: A single unit of execution (one engine invocation)
- JobGraph: Runtime-only DAG of jobs for a calculation
- Recipe implementations: QE, ORCA, PySCF materialization strategies
- JobExecutor: Executes JobGraph with selection mode support

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
from quantumvitas.execution.executor import (
    JobExecutor,
    JobResult,
    ExecutionResult,
    create_executor_with_default_handlers,
)
from quantumvitas.execution.handlers import (
    qe_step_handler,
    pyscf_chain_handler,
    orca_chain_handler,
    vasp_step_handler,
    lammps_step_handler,
    create_handler_map,
)

__all__ = [
    "Job",
    "JobGraph",
    "SelectionMode",
    "compute_job_fingerprint",
    "JobExecutor",
    "JobResult",
    "ExecutionResult",
    "create_executor_with_default_handlers",
    "qe_step_handler",
    "pyscf_chain_handler",
    "orca_chain_handler",
    "vasp_step_handler",
    "lammps_step_handler",
    "create_handler_map",
]
