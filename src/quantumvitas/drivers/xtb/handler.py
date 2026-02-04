"""xTB step handler.

Executes xTB calculations by writing XYZ input, running the xtb
binary via subprocess, and parsing output files.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from quantumvitas.execution.executor import JobResult
from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.relax_artifacts import RelaxArtifactSpec, is_relax_step_type

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


def xtb_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute an xTB step job.

    1. Find step by ULID
    2. Create working directory
    3. Write input.xyz from structure data
    4. Execute xtb via subprocess
    5. Save stdout to xtb.out
    6. Check exit code and output files
    7. Parse results
    8. Return JobResult with relax artifact spec

    Args:
        job: The Job to execute (single step)
        calculation: Calculation context
        engine_registry: Engine registry
        context: Additional context

    Returns:
        JobResult with execution status
    """
    from .writer import write_xyz_from_pymatgen
    from .parser import parse_xtb_stdout, parse_xtbopt_xyz, check_success

    if not job.step_ulids:
        return JobResult(
            job_id=job.id, success=False, error="No step ULIDs in job",
        )

    step_ulid = job.step_ulids[0]
    step = _find_step_by_ulid(calculation, step_ulid)
    if step is None:
        return JobResult(
            job_id=job.id, success=False, error=f"Step not found: {step_ulid}",
        )

    working_dir = job.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)

    # Load structure from project
    structure_ref = calculation.structure
    if structure_ref is None:
        return JobResult(
            job_id=job.id, success=False, error="No structure in calculation",
        )

    try:
        from quantumvitas.io import read_structure
        pmg_structure = read_structure(structure_ref.absolute_path)
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to load structure from {structure_ref.absolute_path}: {e}",
        )

    input_xyz = working_dir / "input.xyz"
    try:
        write_xyz_from_pymatgen(pmg_structure, input_xyz)
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to write input.xyz: {e}",
        )

    # Execute xTB
    timeout = context.get("timeout", 3600)
    try:
        result = subprocess.run(
            job.command,
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return JobResult(
            job_id=job.id, success=False, error="xTB calculation timed out",
        )
    except FileNotFoundError:
        return JobResult(
            job_id=job.id, success=False,
            error="xTB executable not found. Install with: conda install -c conda-forge xtb",
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to execute xTB: {e}",
        )

    # Save stdout + stderr
    (working_dir / "xtb.out").write_text(result.stdout + result.stderr)

    # Check exit code
    if result.returncode != 0:
        stderr_snippet = result.stderr[:1000] if result.stderr else ""
        return JobResult(
            job_id=job.id, success=False,
            error=f"xTB exited with code {result.returncode}: {stderr_snippet}",
        )

    # Parse stdout results
    step_result_data: Dict[str, Any] = {"success": True}
    try:
        parsed_stdout = parse_xtb_stdout(result.stdout)
        step_result_data.update(parsed_stdout)
    except Exception as e:
        logger.warning("Failed to parse xTB stdout: %s", e)

    # For relax: parse optimized geometry and create artifact spec
    gen_type = job.metadata.get("step_type_gen", "relax")
    if gen_type == "relax":
        xtbopt_path = working_dir / "xtbopt.xyz"
        if not xtbopt_path.exists():
            return JobResult(
                job_id=job.id, success=False,
                error="xtbopt.xyz not found after optimization",
            )

        # Check convergence marker
        converged = check_success(working_dir)
        step_result_data["converged"] = converged
        if not converged:
            logger.warning(
                "xTB optimization did not converge (.xtboptok missing) for step %s",
                step_ulid,
            )

        # Parse optimized geometry
        try:
            parsed_geo = parse_xtbopt_xyz(xtbopt_path)
            step_result_data["optimized_energy_Eh"] = parsed_geo.get("energy_Eh")
            step_result_data["optimized_gnorm"] = parsed_geo.get("gnorm")
            step_result_data["n_atoms"] = parsed_geo.get("n_atoms")
        except Exception as e:
            logger.warning("Failed to parse xtbopt.xyz: %s", e)

        # Create relax artifact spec
        step_type_spec = step.step_type_spec if hasattr(step, "step_type_spec") else None
        if step_type_spec and is_relax_step_type(str(step_type_spec)):
            step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                artifact_type="xtb_xyz",
                artifact_path=xtbopt_path,
                step_ulid=step_ulid,
                step_type_spec=str(step_type_spec),
            ).to_dict()

    step_results = {step_ulid: step_result_data}

    return JobResult(
        job_id=job.id,
        success=True,
        step_results=step_results,
    )
