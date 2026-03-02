"""MACE step handler.

Executes MACE calculations as Python subprocess calls.
Each step generates a Python script via writer.py, then
executes it with subprocess.run().
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from qmatsuite.execution.job_graph import Job
from qmatsuite.execution.executor import JobResult
from qmatsuite.execution.relax_artifacts import RelaxArtifactSpec, is_relax_step_type

if TYPE_CHECKING:
    from qmatsuite.calculation.calculation import Calculation
    from qmatsuite.calculation.step import Step
    from qmatsuite.engine.registry import EngineRegistry

logger = logging.getLogger(__name__)


def _find_step_by_ulid(calculation: "Calculation", step_ulid: str) -> Optional["Step"]:
    """Find a step in calculation by its ULID."""
    for step in calculation.steps:
        if step.meta.ulid == step_ulid:
            return step
    return None


def mace_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """Execute a MACE step job.

    1. Find step by ULID
    2. Generate Python script via writer
    3. Write structure file
    4. Execute script via subprocess
    5. Parse results
    6. Return JobResult
    """
    from .writer import write_mace_script

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

    gen_type = job.metadata.get("step_type_gen", "scf")
    script_name = f"{gen_type}.py"

    # Extract step parameters
    params: dict = {}
    if hasattr(step, "params") and step.params:
        params = dict(step.params)
    if hasattr(step, "options") and step.options:
        params.update(step.options)

    # Write structure file
    structure_file = "structure.json"
    _write_structure_file(calculation, working_dir / structure_file)

    # Generate the Python script
    script_path = working_dir / script_name
    try:
        write_mace_script(
            gen_type=gen_type,
            params=params,
            output_path=script_path,
            structure_file=structure_file,
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to generate MACE script: {e}",
        )

    # Execute the script
    timeout = context.get("timeout", 3600)
    python_exe = sys.executable
    try:
        from qmatsuite.core.engines.engine_registry import resolve_active_python
        resolved_py = resolve_active_python("mace")
        if resolved_py and resolved_py.is_file():
            python_exe = str(resolved_py)
    except Exception:
        pass

    try:
        result = subprocess.run(
            [python_exe, script_name],
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return JobResult(
            job_id=job.id, success=False, error="MACE calculation timed out",
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to execute MACE script: {e}",
        )

    if result.returncode != 0:
        stderr_snippet = result.stderr[:1000] if result.stderr else ""
        return JobResult(
            job_id=job.id, success=False,
            error=f"MACE exited with code {result.returncode}: {stderr_snippet}",
        )

    # Parse results
    results_file = working_dir / "results.json"
    step_results = {}

    if results_file.exists():
        try:
            parsed = json.loads(results_file.read_text())
            step_result_data: Dict[str, Any] = {
                "success": True,
                "working_dir": str(working_dir),
                **parsed,
            }

            # Handle relax artifacts
            step_type_spec = step.step_type_spec if hasattr(step, "step_type_spec") else None
            if step_type_spec and is_relax_step_type(str(step_type_spec)):
                step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                    artifact_type="mace_results",
                    artifact_path=results_file,
                    step_ulid=step_ulid,
                    step_type_spec=str(step_type_spec),
                ).to_dict()

            step_results[step_ulid] = step_result_data
        except Exception as e:
            logger.warning(f"Failed to parse results.json: {e}")
            step_results[step_ulid] = {"success": True, "parse_error": str(e)}
    else:
        step_results[step_ulid] = {"success": True, "note": "No results.json found"}

    return JobResult(
        job_id=job.id,
        success=True,
        step_results=step_results,
    )


def _write_structure_file(calculation: "Calculation", output_path: Path) -> None:
    """Write structure to a JSON file readable by ASE."""
    try:
        structure_ref = getattr(calculation, "structure", None)
        if structure_ref is None:
            logger.warning("No structure reference on calculation; skipping structure.json")
            return

        struct_path = getattr(structure_ref, "absolute_path", None)
        if struct_path is None or not Path(struct_path).exists():
            logger.warning(f"Structure file not found at {struct_path}; skipping structure.json")
            return

        from qmatsuite.io import read_structure
        pmg_struct = read_structure(Path(struct_path))

        symbols = [str(s) for s in pmg_struct.species]
        positions = [list(float(x) for x in site.coords) for site in pmg_struct]
        cell = [[float(x) for x in row] for row in pmg_struct.lattice.matrix]
        pbc = list(pmg_struct.lattice.pbc) if hasattr(pmg_struct.lattice, "pbc") else [True, True, True]

        data = {
            "symbols": symbols,
            "positions": positions,
            "cell": cell,
            "pbc": pbc,
        }
        output_path.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.warning(f"Could not write structure file: {e}")
