"""ABINIT step handler.

Executes ABINIT calculations by:
1. Writing input file (.abi)
2. Running abinit subprocess
3. Parsing output file (.abo)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from quantumvitas.execution.executor import JobResult
from quantumvitas.execution.job_graph import Job

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.step import Step
    from quantumvitas.engine.registry import EngineRegistry

logger = logging.getLogger(__name__)


def _find_step_by_ulid(
    calculation: "Calculation", step_ulid: str
) -> Optional["Step"]:
    """Find a step in calculation by its ULID."""
    for step in calculation.steps:
        if step.meta.ulid == step_ulid:
            return step
    return None


def _resolve_abinit_bin(binary_name: str = "abinit") -> Optional[str]:
    """Resolve abinit binary using centralized discovery."""
    from quantumvitas.core.engines.discovery import discover_engine

    result = discover_engine("abinit")
    if result.available and result.executable_path:
        bin_dir = result.executable_path.parent
        candidate = bin_dir / binary_name
        if candidate.is_file():
            return str(candidate)
    # Fallback to PATH
    found = shutil.which(binary_name)
    return found


def abinit_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """Execute an ABINIT step job.

    Args:
        job: Job object with command and working directory
        calculation: Parent calculation
        engine_registry: Engine registry (unused for ABINIT)
        context: Execution context with timeout, etc.

    Returns:
        JobResult with success status and parsed artifacts
    """
    if not job.step_ulids:
        return JobResult(
            job_id=job.id, success=False, error="No step ULIDs in job",
        )

    step_ulid = job.step_ulids[0]
    step = _find_step_by_ulid(calculation, step_ulid)
    if step is None:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Step not found: {step_ulid}",
        )

    # Resolve ABINIT binary
    abinit_bin = _resolve_abinit_bin("abinit")
    if abinit_bin is None:
        return JobResult(
            job_id=job.id, success=False,
            error="ABINIT binary not found. Ensure ABINIT is installed.",
        )

    working_dir = job.working_dir
    timeout = context.get("timeout", 3600)

    # Get the input file from job metadata or infer from job id
    step_prefix = job.metadata.get("step_prefix", job.id)
    input_file = working_dir / f"{step_prefix}.abi"
    output_file = working_dir / f"{step_prefix}.abo"

    if not input_file.exists():
        return JobResult(
            job_id=job.id, success=False,
            error=f"Input file not found: {input_file}",
        )

    # Execute ABINIT
    # ABINIT reads from stdin by default, so we specify input file via redirect
    cmd = [abinit_bin, str(input_file)]
    logger.info("Running: %s in %s", " ".join(cmd), working_dir)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return JobResult(
            job_id=job.id, success=False, error="ABINIT calculation timed out",
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False, error=f"ABINIT execution failed: {e}",
        )

    # Parse results
    step_result_data: Dict[str, Any] = {}

    if output_file.exists():
        try:
            from .parser import parse_abinit_output
            parsed = parse_abinit_output(output_file)

            # Extract key results from first dataset
            if 1 in parsed.datasets:
                ds = parsed.datasets[1]
                step_result_data["total_energy_Ha"] = ds.total_energy
                step_result_data["total_energy_eV"] = ds.total_energy_eV
                step_result_data["n_iterations"] = ds.n_iterations
                step_result_data["converged"] = ds.converged

                if ds.fermi_energy is not None:
                    step_result_data["fermi_energy_Ha"] = ds.fermi_energy

                if ds.forces is not None:
                    step_result_data["max_force_Ha_Bohr"] = ds.forces.max_force

                if ds.stress is not None:
                    step_result_data["pressure_GPa"] = ds.stress.pressure_gpa

                if ds.final_structure is not None:
                    step_result_data["final_acell"] = ds.final_structure.acell

            step_result_data["calculation_type"] = parsed.calculation_type
            step_result_data["abinit_version"] = parsed.version
            step_result_data["wall_time_s"] = parsed.wall_time
            step_result_data["warnings"] = parsed.warnings

        except Exception as e:
            logger.warning("Failed to parse ABINIT output: %s", e)
            step_result_data["parse_error"] = str(e)

    # Check for success
    success = result.returncode == 0

    # ABINIT often writes to log file named <prefix>.log or directly to .abo
    if not success:
        stderr_snippet = result.stderr[:1000] if result.stderr else ""
        stdout_snippet = result.stdout[:1000] if result.stdout else ""
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"ABINIT exited with code {result.returncode}: {stderr_snippet or stdout_snippet}",
            step_results={step_ulid: step_result_data},
        )

    step_result_data["success"] = True

    return JobResult(
        job_id=job.id,
        success=True,
        step_results={step_ulid: step_result_data},
    )
