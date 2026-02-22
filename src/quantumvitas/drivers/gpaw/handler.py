"""GPAW step handler.

Executes GPAW calculations as Python subprocess calls.
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

from quantumvitas.execution.job_graph import Job
from quantumvitas.execution.executor import JobResult
from quantumvitas.execution.relax_artifacts import RelaxArtifactSpec, is_relax_step_type

if TYPE_CHECKING:
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.calculation.step import Step
    from quantumvitas.engine.registry import EngineRegistry

logger = logging.getLogger(__name__)


def _find_step_by_ulid(calculation: "Calculation", step_ulid: str) -> Optional["Step"]:
    """Find a step in calculation by its ULID."""
    for step in calculation.steps:
        if step.meta.ulid == step_ulid:
            return step
    return None


def gpaw_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a GPAW step job.

    1. Find step by ULID
    2. Generate Python script via writer
    3. Write structure file
    4. Execute script via subprocess
    5. Parse results
    6. Return JobResult

    Args:
        job: The Job to execute (single step)
        calculation: Calculation context
        engine_registry: Engine registry
        context: Additional context

    Returns:
        JobResult with execution status
    """
    from .writer import write_gpaw_script
    from .parser import parse_results_json

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

    # Determine gen type from metadata
    gen_type = job.metadata.get("step_type_gen", "scf")
    script_name = job.metadata.get("script_name", f"{gen_type}.py")

    # Extract step parameters
    params = {}
    if hasattr(step, "params") and step.params:
        params = dict(step.params)
    if hasattr(step, "options") and step.options:
        params.update(step.options)

    # Set txt/gpw file names based on gen type
    params.setdefault("txt_file", f"{gen_type}.txt")
    params.setdefault("gpw_file", f"{gen_type}.gpw")

    # Determine restart source for chaining steps
    restart_from = None
    if gen_type in ("bandspw", "dos", "nscf"):
        scf_gpw = working_dir / "scf.gpw"
        if scf_gpw.exists():
            restart_from = "scf.gpw"

    # Write structure file if needed (for SCF/relax/MD, not for bands/dos from restart)
    structure_file = "structure.json"
    if restart_from is None:
        _write_structure_file(calculation, working_dir / structure_file)

    # Generate the Python script
    script_path = working_dir / script_name
    try:
        write_gpaw_script(
            gen_type=gen_type,
            params=params,
            output_path=script_path,
            structure_file=structure_file,
            restart_from=restart_from,
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to generate GPAW script: {e}",
        )

    # Execute the script
    timeout = context.get("timeout", 3600)
    python_exe = sys.executable
    try:
        from quantumvitas.core.engines.engine_registry import resolve_active_python

        resolved_py = resolve_active_python("gpaw")
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
            job_id=job.id, success=False, error="GPAW calculation timed out",
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to execute GPAW script: {e}",
        )

    if result.returncode != 0:
        stderr_snippet = result.stderr[:1000] if result.stderr else ""
        return JobResult(
            job_id=job.id, success=False,
            error=f"GPAW exited with code {result.returncode}: {stderr_snippet}",
        )

    # Parse results
    results_file = working_dir / "results.json"
    step_results = {}

    if results_file.exists():
        try:
            parsed = parse_results_json(results_file)
            step_result_data: Dict[str, Any] = {
                "success": True,
                "working_dir": str(working_dir),
                **parsed,
            }

            # Handle relax artifacts
            step_type_spec = step.step_type_spec if hasattr(step, "step_type_spec") else None
            if step_type_spec and is_relax_step_type(str(step_type_spec)):
                step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                    artifact_type="gpaw_results",
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
    """Write structure to a JSON file readable by ASE.

    calculation.structure is a StructureRef (pointer to a structure file),
    not an actual atomic structure object.  We must load the real structure
    from disk and convert it to a format ASE can read.
    """
    try:
        structure_ref = getattr(calculation, "structure", None)
        if structure_ref is None:
            logger.warning("No structure reference on calculation; skipping structure.json")
            return

        # Load the real pymatgen structure from the on-disk JSON
        struct_path = getattr(structure_ref, "absolute_path", None)
        if struct_path is None or not Path(struct_path).exists():
            logger.warning(f"Structure file not found at {struct_path}; skipping structure.json")
            return

        from quantumvitas.io import read_structure
        pmg_struct = read_structure(Path(struct_path))

        # Convert pymatgen Structure/Molecule → ASE-compatible dict
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
