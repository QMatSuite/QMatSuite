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

from qmatsuite.execution.executor import JobResult
from qmatsuite.execution.job_graph import Job

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


def _resolve_abinit_bin(binary_name: str = "abinit") -> Optional[str]:
    """Resolve abinit binary using centralized discovery."""
    try:
        from qmatsuite.core.engines.engine_registry import resolve_active_binary

        resolved = resolve_active_binary("abinit", binary_name=binary_name)
        if resolved and resolved.is_file():
            return str(resolved)
    except Exception:
        pass

    from qmatsuite.core.engines.discovery import discover_engine

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
    working_dir.mkdir(parents=True, exist_ok=True)
    timeout = context.get("timeout", 3600)

    # Get the input file from job metadata or infer from job id
    step_prefix = job.metadata.get("step_prefix", job.id)
    input_file = working_dir / f"{step_prefix}.abi"
    output_file = working_dir / f"{step_prefix}.abo"

    # Write .abi input file if it doesn't exist yet
    if not input_file.exists():
        try:
            _write_abinit_input(step, calculation, input_file)
        except Exception as e:
            return JobResult(
                job_id=job.id, success=False,
                error=f"Failed to write ABINIT input: {e}",
            )

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


def _write_abinit_input(
    step: "Step",
    calculation: "Calculation",
    output_path: Path,
) -> None:
    """Write ABINIT .abi input file from step params + calculation structure."""
    import shutil as _shutil
    from .io.abinit_input import write_abinit_text

    # Load parameters from step YAML (demo projects store params at top level)
    params: dict = {}
    try:
        from qmatsuite.core.yamldoc import StepDoc
        step_yaml = calculation.dir / "steps" / f"{step.meta.slug}.step.yaml"
        if step_yaml.exists():
            doc = StepDoc.load(step_yaml)
            data = doc.to_dict()
            params = dict(data.get("parameters", {}))
    except Exception as e:
        logger.warning("Failed to load step YAML params: %s", e)
    # Fallback: try step.options
    if not params:
        if hasattr(step, "options") and step.options:
            params = dict(step.options)

    # Stage pseudopotential files into working directory
    working_dir = output_path.parent
    pp_dirpath = params.get("pp_dirpath", "./")
    pseudos_val = params.get("pseudos", "")
    if pseudos_val and isinstance(pseudos_val, str):
        pp_files = [f.strip() for f in pseudos_val.split(",")]
    elif isinstance(pseudos_val, list):
        pp_files = pseudos_val
    else:
        pp_files = []

    if pp_files:
        # Resolve pp_dirpath relative to working_dir, create if needed
        if Path(pp_dirpath).is_absolute():
            pp_target = Path(pp_dirpath)
        else:
            pp_target = working_dir / pp_dirpath
        pp_target.mkdir(parents=True, exist_ok=True)

        # Build search directories for PP files
        pp_search_dirs: list[Path] = []
        from qmatsuite.core.engines.discovery import discover_engine
        result = discover_engine("abinit")
        if result.available and result.executable_path:
            abinit_root = result.executable_path.parent.parent
            # Search build directory for test PPs (PseudoDojo, GTH, etc.)
            build_root = abinit_root.parent.parent / "_build" / "abinit"
            for psp_dir in sorted(build_root.glob("abinit-*/tests/Pspdir")):
                pp_search_dirs.append(psp_dir)
                # Add subdirectories (PseudoDojo, GTH, etc.)
                for sub in sorted(psp_dir.iterdir()):
                    if sub.is_dir():
                        pp_search_dirs.append(sub)

        for pp_file in pp_files:
            dst = pp_target / pp_file
            if dst.exists():
                continue
            # Search in known locations
            found = False
            for search_dir in pp_search_dirs:
                src = search_dir / pp_file
                if src.exists():
                    _shutil.copy2(src, dst)
                    found = True
                    logger.info("Staged PP %s from %s", pp_file, search_dir)
                    break
            if not found:
                logger.warning("PP file %s not found in any search directory", pp_file)

    # Load structure from calculation
    structure_dict: dict = {}
    structure_ref = getattr(calculation, "structure", None)
    if structure_ref is not None:
        struct_path = getattr(structure_ref, "absolute_path", None)
        if struct_path and Path(struct_path).exists():
            try:
                from qmatsuite.io import read_structure
                pmg_struct = read_structure(Path(struct_path))
                structure_dict = {
                    "species": [str(s) for s in pmg_struct.species],
                    "frac_coords": [list(site.frac_coords) for site in pmg_struct],
                    "lattice": [
                        [float(x) for x in row]
                        for row in pmg_struct.lattice.matrix
                    ],
                }
            except Exception as e:
                logger.warning("Failed to load structure for ABINIT input: %s", e)

    fragment = {"params": params, "structure": structure_dict}
    text = write_abinit_text(fragment)
    output_path.write_text(text)

