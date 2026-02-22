"""Gaussian step handler.

Executes Gaussian calculations by writing .gjf input files, running the
Gaussian binary (g09/g16) via subprocess, and parsing output .log files.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from qmatsuite.execution.executor import JobResult
from qmatsuite.execution.job_graph import Job
from qmatsuite.execution.relax_artifacts import RelaxArtifactSpec, is_relax_step_type

if TYPE_CHECKING:
    from qmatsuite.calculation.calculation import Calculation
    from qmatsuite.calculation.step import Step
    from qmatsuite.engine.registry import EngineRegistry

logger = logging.getLogger(__name__)


def _find_step_by_ulid(
    calculation: "Calculation", step_ulid: str
) -> Optional["Step"]:
    """Find a step in calculation by its ULID."""
    for step in calculation.steps:
        if step.meta.ulid == step_ulid:
            return step
    return None


def _find_gaussian_binary(project_root: Optional[Path] = None) -> Optional[Path]:
    """Find the Gaussian binary (g09 or g16).

    Uses centralized engine discovery which searches:
    1. Bundled: .qmatsuite/engines/gaussian/*/g09 or g16
    2. Environment: GAUSS_EXEDIR/g09, g09root/g09/g09
    3. System PATH
    """
    from qmatsuite.core.engines.discovery import discover_engine, clear_discovery_cache

    # Clear cache to ensure fresh discovery
    clear_discovery_cache()

    # Use centralized discovery with project_root
    result = discover_engine("gaussian", project_root=project_root)
    if result.available and result.executable_path:
        return result.executable_path

    # Fallback: also try discovering with cwd as project_root
    # This helps when bundled engines are in repo root but project is elsewhere
    cwd = Path.cwd()
    if project_root != cwd:
        result = discover_engine("gaussian", project_root=cwd, use_cache=False)
        if result.available and result.executable_path:
            return result.executable_path

    # Final fallback: try without any project_root
    result = discover_engine("gaussian", use_cache=False)
    if result.available and result.executable_path:
        return result.executable_path

    return None


def _setup_gaussian_env(binary_path: Path) -> Dict[str, str]:
    """Setup environment variables for Gaussian execution."""
    env = os.environ.copy()

    # Determine root and exedir from binary path
    # Binary is typically at: .../gaussian09/g09/g09
    binary_dir = binary_path.parent  # g09/

    # Set GAUSS_EXEDIR to directory containing the binary
    env["GAUSS_EXEDIR"] = str(binary_dir)

    # Set scratch directory
    if "GAUSS_SCRDIR" not in env:
        env["GAUSS_SCRDIR"] = "/tmp"

    # Add to PATH
    path = env.get("PATH", "")
    env["PATH"] = f"{binary_dir}:{path}"

    return env


def gaussian_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a Gaussian step job.

    1. Find step by ULID
    2. Create working directory
    3. Write input.gjf from structure data
    4. Execute Gaussian via subprocess
    5. Save stdout to output.log
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
    from .writer import write_gaussian_input
    from .parser import parse_log_file

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
        from qmatsuite.io import read_structure
        pmg_structure = read_structure(structure_ref.absolute_path)
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to load structure from {structure_ref.absolute_path}: {e}",
        )

    # Get step parameters
    params: dict = {}
    if hasattr(step, "params") and step.params:
        params = dict(step.params)

    # Determine gen type
    gen_type = job.metadata.get("step_type_gen", "scf")

    # Write input file
    input_gjf = working_dir / "input.gjf"
    output_log = working_dir / "output.log"

    try:
        write_gaussian_input(
            structure=pmg_structure,
            output_path=input_gjf,
            gen_type=gen_type,
            method=params.get("method", "HF"),
            basis=params.get("basis", "STO-3G"),
            charge=params.get("charge", 0),
            multiplicity=params.get("multiplicity", 1),
            mem=params.get("mem", "500MB"),
            nproc=params.get("nproc", 1),
            td_nstates=params.get("td_nstates", 3),
            opt_tight=params.get("opt_tight", False),
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to write input.gjf: {e}",
        )

    # Find Gaussian binary
    project_root = context.get("project_root")
    gaussian_bin = _find_gaussian_binary(project_root)
    if gaussian_bin is None:
        return JobResult(
            job_id=job.id, success=False,
            error="Gaussian executable not found. Install Gaussian and set GAUSS_EXEDIR.",
        )

    # Setup environment
    env = _setup_gaussian_env(gaussian_bin)

    # Execute Gaussian
    timeout = context.get("timeout", 3600)
    try:
        # Gaussian reads from stdin when invoked as: g09 < input.gjf > output.log
        with open(input_gjf, "r") as stdin_file:
            result = subprocess.run(
                [str(gaussian_bin)],
                stdin=stdin_file,
                capture_output=True,
                text=True,
                cwd=str(working_dir),
                env=env,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return JobResult(
            job_id=job.id, success=False, error="Gaussian calculation timed out",
        )
    except FileNotFoundError:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Gaussian executable not found at {gaussian_bin}",
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to execute Gaussian: {e}",
        )

    # Save stdout as output.log
    output_log.write_text(result.stdout + result.stderr)

    # Check exit code
    if result.returncode != 0:
        stderr_snippet = result.stderr[:1000] if result.stderr else ""
        return JobResult(
            job_id=job.id, success=False,
            error=f"Gaussian exited with code {result.returncode}: {stderr_snippet}",
        )

    # Parse output
    step_result_data: Dict[str, Any] = {"success": True}
    try:
        parsed = parse_log_file(output_log)
        step_result_data.update(parsed)

        # Check for normal termination
        if not parsed.get("normal_termination", False):
            return JobResult(
                job_id=job.id, success=False,
                error=f"Gaussian did not terminate normally: {parsed.get('termination_message', 'unknown')}",
            )
    except Exception as e:
        logger.warning("Failed to parse Gaussian output: %s", e)

    # For relax: create artifact spec
    if gen_type == "relax":
        opt_result = step_result_data.get("optimization", {})
        step_result_data["converged"] = opt_result.get("converged", False)

        if not opt_result.get("converged", False):
            logger.warning(
                "Gaussian optimization did not converge for step %s",
                step_ulid,
            )

        # Create relax artifact spec
        step_type_spec = step.step_type_spec if hasattr(step, "step_type_spec") else None
        if step_type_spec and is_relax_step_type(str(step_type_spec)):
            step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                artifact_type="gaussian_log",
                artifact_path=output_log,
                step_ulid=step_ulid,
                step_type_spec=str(step_type_spec),
            ).to_dict()

    step_results = {step_ulid: step_result_data}

    return JobResult(
        job_id=job.id,
        success=True,
        step_results=step_results,
    )
