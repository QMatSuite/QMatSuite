"""Siesta step handler.

Executes Siesta calculations by writing FDF input, staging
pseudopotentials, running the siesta binary via subprocess,
and parsing the output files.
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


def _find_siesta_executable() -> str:
    """Find the siesta executable path."""
    found = shutil.which("siesta")
    if found:
        return found
    return "siesta"


def siesta_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a Siesta step job.

    1. Find step by ULID
    2. Create working directory
    3. Generate FDF input file via writer
    4. Stage pseudopotential files
    5. Execute siesta via subprocess
    6. Check 0_NORMAL_EXIT
    7. Parse output files
    8. Return JobResult

    Args:
        job: The Job to execute (single step)
        calculation: Calculation context
        engine_registry: Engine registry
        context: Additional context

    Returns:
        JobResult with execution status
    """
    from .parser import parse_siesta_workdir
    from .writer import write_fdf

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
    system_label = job.metadata.get("system_label", gen_type)
    fdf_name = job.metadata.get("fdf_name", f"{system_label}.fdf")

    # Load parameters from step YAML
    params: dict[str, Any] = {}
    try:
        from quantumvitas.core.yamldoc import StepDoc
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

    # Build species and atoms from calculation structure
    species, atoms, lattice_constant, lattice_vectors, coord_format = (
        _extract_structure(calculation, params)
    )

    # Configure step-type-specific parameters
    fdf_params = _configure_step_params(gen_type, params)

    # Generate FDF input file
    fdf_path = working_dir / fdf_name
    try:
        write_fdf(
            output_path=fdf_path,
            system_name=params.get("system_name", system_label),
            system_label=system_label,
            species=species,
            lattice_constant=lattice_constant,
            lattice_vectors=lattice_vectors,
            atoms=atoms,
            coord_format=coord_format,
            params=fdf_params,
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to generate FDF input: {e}",
        )

    # Stage pseudopotential files
    pp_dir = params.get("pseudopotential_dir")
    if pp_dir:
        _stage_pseudopotentials(Path(pp_dir), species, working_dir)
    # Auto-stage from repo's bundled pseudopotentials if not already staged
    _auto_stage_pseudopotentials(species, working_dir)

    # Execute siesta
    siesta_bin = _find_siesta_executable()
    out_path = working_dir / f"{system_label}.out"
    timeout = context.get("timeout", 3600)

    try:
        with open(fdf_path) as stdin_file, open(out_path, "w") as stdout_file:
            result = subprocess.run(
                [siesta_bin],
                stdin=stdin_file,
                stdout=stdout_file,
                stderr=subprocess.PIPE,
                cwd=str(working_dir),
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return JobResult(
            job_id=job.id, success=False, error="Siesta calculation timed out",
        )
    except FileNotFoundError:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Siesta executable not found: {siesta_bin}",
        )
    except Exception as e:
        return JobResult(
            job_id=job.id, success=False,
            error=f"Failed to execute Siesta: {e}",
        )

    if result.returncode != 0:
        stderr_snippet = result.stderr.decode("utf-8", errors="replace")[:1000]
        return JobResult(
            job_id=job.id, success=False,
            error=f"Siesta exited with code {result.returncode}: {stderr_snippet}",
        )

    # Check normal exit
    normal_exit = (working_dir / "0_NORMAL_EXIT").exists()
    if not normal_exit:
        return JobResult(
            job_id=job.id, success=False,
            error="Siesta did not produce 0_NORMAL_EXIT marker",
        )

    # Parse results
    step_results: dict[str, Any] = {}
    try:
        parsed = parse_siesta_workdir(working_dir, system_label)
        step_results[step_ulid] = {
            "success": True,
            "working_dir": str(working_dir),
            **parsed,
        }
    except Exception as e:
        logger.warning("Failed to parse Siesta output: %s", e)
        step_results[step_ulid] = {"success": True, "parse_error": str(e)}

    return JobResult(
        job_id=job.id,
        success=True,
        step_results=step_results,
    )


def _extract_structure(
    calculation: "Calculation", params: dict[str, Any]
) -> tuple[list, list, float, list, str]:
    """Extract structure data from calculation for FDF generation."""
    species = params.get("species", [])
    atoms = params.get("atoms", [])
    lattice_constant = params.get("lattice_constant", 1.0)
    lattice_vectors = params.get("lattice_vectors", [
        [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0],
    ])
    coord_format = params.get("coord_format", "Ang")

    # Try to get from calculation structure if not in params
    if not species and hasattr(calculation, "structure") and calculation.structure:
        structure_ref = calculation.structure
        # StructureRef only has meta + absolute_path; load actual pymatgen Structure
        struct_path = getattr(structure_ref, "absolute_path", None)
        if struct_path and Path(struct_path).exists():
            try:
                from quantumvitas.io import read_structure
                pmg_struct = read_structure(Path(struct_path))
                symbols = [str(s) for s in pmg_struct.species]
                unique_symbols = list(dict.fromkeys(symbols))
                species = [
                    {"index": i + 1, "atomic_number": _symbol_to_z(sym), "label": sym}
                    for i, sym in enumerate(unique_symbols)
                ]
                symbol_to_idx = {sym: i + 1 for i, sym in enumerate(unique_symbols)}
                atoms = [
                    {
                        "x": float(site.coords[0]),
                        "y": float(site.coords[1]),
                        "z": float(site.coords[2]),
                        "species_index": symbol_to_idx[str(site.specie)],
                    }
                    for site in pmg_struct
                ]
                # Extract lattice
                lattice_vectors = [
                    [float(x) for x in row]
                    for row in pmg_struct.lattice.matrix
                ]
                lattice_constant = 1.0  # Vectors already in Angstrom
            except Exception as e:
                logger.warning("Failed to load structure from %s: %s", struct_path, e)

    return species, atoms, lattice_constant, lattice_vectors, coord_format


def _configure_step_params(
    gen_type: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Configure FDF parameters based on step type."""
    fdf_params: dict[str, Any] = {}

    # Copy relevant FDF parameters from step params
    fdf_keys = [
        "PAO.BasisSize", "PAO.EnergyShift", "MeshCutoff",
        "MaxSCFIterations", "DM.MixingWeight", "DM.Tolerance",
        "SolutionMethod", "XC.functional", "XC.authors",
        "WriteForces", "WriteCoorXmol", "WriteMDXmol", "WriteMDhistory",
        "DM.UseSaveDM", "kgrid", "ProjectedDensityOfStates", "BandLines",
        "BandLinesScale",
    ]
    for key in fdf_keys:
        if key in params:
            fdf_params[key] = params[key]

    if gen_type == "relax":
        fdf_params["MD.TypeOfRun"] = params.get("MD.TypeOfRun", "CG")
        fdf_params["MD.NumCGsteps"] = params.get("MD.NumCGsteps", 30)
        if "MD.MaxForceTol" in params:
            fdf_params["MD.MaxForceTol"] = params["MD.MaxForceTol"]
        if "MD.VariableCell" in params:
            fdf_params["MD.VariableCell"] = params["MD.VariableCell"]
        if "MD.MaxStressTol" in params:
            fdf_params["MD.MaxStressTol"] = params["MD.MaxStressTol"]
    elif gen_type == "md":
        fdf_params["MD.TypeOfRun"] = params.get("MD.TypeOfRun", "Verlet")
        fdf_params["MD.Steps"] = params.get("MD.Steps", 100)
        if "MD.InitialTemperature" in params:
            fdf_params["MD.InitialTemperature"] = params["MD.InitialTemperature"]
        if "MD.TargetTemperature" in params:
            fdf_params["MD.TargetTemperature"] = params["MD.TargetTemperature"]
        if "MD.LengthTimeStep" in params:
            fdf_params["MD.LengthTimeStep"] = params["MD.LengthTimeStep"]

    return fdf_params


def _stage_pseudopotentials(
    pp_dir: Path, species: list[dict], working_dir: Path
) -> None:
    """Copy pseudopotential files into the working directory."""
    for sp in species:
        label = sp["label"]
        for ext in (".psml", ".psf"):
            src = pp_dir / f"{label}{ext}"
            if src.exists():
                dst = working_dir / f"{label}{ext}"
                if not dst.exists():
                    shutil.copy2(src, dst)
                break


def _auto_stage_pseudopotentials(
    species: list[dict], working_dir: Path
) -> None:
    """Auto-stage pseudopotentials from known repo locations if not already present."""
    # Search in repo's bundled pseudopotentials
    repo_root = Path(__file__).resolve().parents[4]  # src/quantumvitas/drivers/siesta/handler.py -> repo root
    pp_search_dirs = [
        repo_root / "docs" / "engines" / "siesta" / "pseudopotentials",
    ]
    for sp in species:
        label = sp["label"]
        # Skip if already staged
        if any((working_dir / f"{label}{ext}").exists() for ext in (".psml", ".psf")):
            continue
        for search_dir in pp_search_dirs:
            if not search_dir.is_dir():
                continue
            for ext in (".psml", ".psf"):
                src = search_dir / f"{label}{ext}"
                if src.exists():
                    dst = working_dir / f"{label}{ext}"
                    shutil.copy2(src, dst)
                    logger.info("Auto-staged PP %s from %s", f"{label}{ext}", search_dir)
                    break


# Minimal periodic table for structure extraction
_SYMBOL_TO_Z = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8,
    "F": 9, "Ne": 10, "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15,
    "S": 16, "Cl": 17, "Ar": 18, "K": 19, "Ca": 20, "Sc": 21, "Ti": 22,
    "V": 23, "Cr": 24, "Mn": 25, "Fe": 26, "Co": 27, "Ni": 28, "Cu": 29,
    "Zn": 30, "Ga": 31, "Ge": 32, "As": 33, "Se": 34, "Br": 35, "Kr": 36,
}


def _symbol_to_z(symbol: str) -> int:
    """Convert element symbol to atomic number."""
    return _SYMBOL_TO_Z.get(symbol, 0)
