"""
Psi4 subprocess runner.

This module is the subprocess entrypoint for Psi4 calculations.
It is executed by the Psi4 engine via subprocess, NOT imported by the daemon.

Psi4 is Python-native, so the runner imports psi4 and uses its Python API
directly. Unlike PySCF which uses checkpoint files for chain state, Psi4
passes wavefunction objects via the ref_wfn parameter in-memory.

Exit codes:
    0 - Success
    1 - Calculation completed but did not converge
    2 - Calculation failed (error)
    3 - Invalid input / setup error
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional


def setup_environment(job: Dict[str, Any]) -> None:
    """Set Psi4 environment variables from job resources."""
    resources = job.get("resources", {})

    max_memory = resources.get("max_memory_mb")
    if max_memory:
        os.environ["PSI_SCRATCH"] = resources.get("scratch_dir", "/tmp")

    threads = resources.get("threads")
    if threads:
        os.environ["OMP_NUM_THREADS"] = str(threads)


def build_molecule(params: Dict[str, Any]):
    """
    Build a psi4 molecule from parameters.

    Prefers structure_path (canonical path from SSOT) over raw atoms list.

    Args:
        params: Dict with structure_path or atoms, plus charge, spin, basis, unit

    Returns:
        psi4 Molecule object

    Raises:
        ValueError: If structure input is missing or invalid
    """
    import psi4

    charge = params.get("charge", 0)
    multiplicity = params.get("multiplicity", 1)
    # If spin is given (2S), convert to multiplicity (2S+1)
    if "spin" in params and "multiplicity" not in params:
        multiplicity = params["spin"] + 1
    symmetry = params.get("symmetry", "c1")

    atoms = []

    if "structure_path" in params:
        structure_path = Path(params["structure_path"])
        if not structure_path.exists():
            raise ValueError(f"Structure file does not exist: {structure_path}")

        from quantumvitas.io.structure_io import read_structure
        from pymatgen.core import Molecule as PMGMolecule

        structure = read_structure(structure_path)

        if not isinstance(structure, PMGMolecule):
            raise ValueError(f"Expected Molecule for Psi4, got {type(structure)}")

        if len(structure) == 0:
            raise ValueError(f"Structure has no atoms: {structure_path}")

        for site in structure:
            coords_list = list(site.coords)
            if len(coords_list) < 3:
                raise ValueError(
                    f"Structure site has invalid coordinates: {coords_list}"
                )
            atoms.append({
                "symbol": site.species_string,
                "x": float(coords_list[0]),
                "y": float(coords_list[1]),
                "z": float(coords_list[2]),
            })

        if charge == 0:
            charge = structure.charge
        if multiplicity == 1 and "multiplicity" not in params and "spin" not in params:
            multiplicity = structure.spin_multiplicity

    elif "atoms" in params:
        raw_atoms = params["atoms"]
        if not raw_atoms:
            raise ValueError("Missing structure input: atoms list is empty")
        for atom in raw_atoms:
            symbol = atom.get("symbol", atom.get("element", "X"))
            if "coords" in atom:
                coords = atom["coords"]
                if len(coords) != 3:
                    raise ValueError(
                        f"Atom {symbol} coordinates must have 3 elements, got {len(coords)}"
                    )
                atoms.append({"symbol": symbol, "x": coords[0], "y": coords[1], "z": coords[2]})
            else:
                atoms.append({
                    "symbol": symbol,
                    "x": float(atom.get("x", 0.0)),
                    "y": float(atom.get("y", 0.0)),
                    "z": float(atom.get("z", 0.0)),
                })
    else:
        raise ValueError("Missing structure input: expected structure_path or atoms in parameters")

    if not atoms:
        raise ValueError("Invalid atoms: empty after processing")

    # Build psi4 geometry string
    lines = [f"    {charge} {multiplicity}"]
    for a in atoms:
        lines.append(f"    {a['symbol']:2s}  {a['x']:14.8f}  {a['y']:14.8f}  {a['z']:14.8f}")
    if symmetry:
        lines.append(f"    symmetry {symmetry}")
    lines.append("    units angstrom")
    lines.append("    no_reorient")
    lines.append("    no_com")

    geom_str = "\n".join(lines)
    mol = psi4.geometry(f"\n{geom_str}\n")
    return mol


def run_scf(params: Dict[str, Any], working_dir: Path) -> Dict[str, Any]:
    """
    Run Psi4 SCF (HF or DFT) calculation.

    Args:
        params: Calculation parameters
        working_dir: Working directory for output

    Returns:
        Dictionary with results including wfn_object for chain state
    """
    import psi4

    start_time = time.time()
    results: Dict[str, Any] = {
        "success": False,
        "error": None,
        "execution_time": 0.0,
    }

    # Build molecule
    try:
        mol = build_molecule(params)
    except Exception as e:
        results["error"] = f"Failed to build molecule: {e}"
        results["execution_time"] = time.time() - start_time
        return results

    # Setup Psi4 environment
    memory_mb = params.get("memory_mb", 500)
    nthreads = params.get("nthreads", 1)
    psi4.set_memory(f"{memory_mb} MB")
    psi4.set_num_threads(nthreads)

    output_file = working_dir / "output.dat"
    psi4.core.set_output_file(str(output_file), False)

    # Determine method
    method = params.get("method", "scf").lower()
    basis = params.get("basis", "sto-3g")

    # Map common method names to psi4 method strings
    method_map = {
        "hf": "scf",
        "rhf": "scf",
        "uhf": "scf",
        "rohf": "scf",
        "dft": "scf",
        "rks": "scf",
        "uks": "scf",
    }
    psi4_method = method_map.get(method, method)

    # Set options
    options = {
        "basis": basis,
        "scf_type": params.get("scf_type", "df"),
    }

    # Reference type
    if method in ("uhf", "uks"):
        options["reference"] = "uhf"
    elif method in ("rohf", "roks"):
        options["reference"] = "rohf"
    else:
        options["reference"] = params.get("reference", "rhf")

    # DFT functional
    xc = params.get("xc", params.get("functional", None))
    if xc:
        psi4_method = xc.lower()

    # Convergence
    if "e_convergence" in params:
        options["e_convergence"] = params["e_convergence"]
    if "d_convergence" in params:
        options["d_convergence"] = params["d_convergence"]
    if "maxiter" in params:
        options["maxiter"] = params["maxiter"]

    # TDDFT support: save JK if needed for later TD step
    if params.get("save_jk", False):
        options["save_jk"] = True

    psi4.set_options(options)

    # Run SCF
    try:
        energy, wfn = psi4.energy(f"{psi4_method}/{basis}", return_wfn=True, molecule=mol)
    except Exception as e:
        results["error"] = f"SCF calculation failed: {e}"
        results["execution_time"] = time.time() - start_time
        return results

    # Check convergence
    converged = True
    try:
        n_iterations = int(psi4.core.variable("SCF ITERATIONS"))
    except Exception:
        n_iterations = 0

    # Collect psi4 variables
    psi4_vars = {}
    try:
        for k, v in psi4.core.variables().items():
            psi4_vars[k] = float(v) if isinstance(v, (int, float)) else str(v)
    except Exception:
        pass

    # Build results
    results["success"] = converged
    results["energy"] = float(energy)
    results["energy_unit"] = "Hartree"
    results["converged"] = converged
    results["method"] = method
    results["basis"] = basis
    results["n_iterations"] = n_iterations
    results["n_atoms"] = mol.natom()
    results["n_electrons"] = int(2 * wfn.nalpha()) if wfn.same_a_b_orbs() else int(wfn.nalpha() + wfn.nbeta())
    results["psi4_variables"] = psi4_vars
    results["execution_time"] = time.time() - start_time

    # Save wavefunction
    try:
        wfn_path = working_dir / "wavefunction.npy"
        wfn.to_file(str(wfn_path))
    except Exception:
        pass

    # Store wfn object for chain state (not serialized)
    results["wfn_object"] = wfn

    return results


def run_mp2(params: Dict[str, Any], wfn, working_dir: Path) -> Dict[str, Any]:
    """
    Run Psi4 MP2 calculation using a reference wavefunction.

    Args:
        params: Calculation parameters
        wfn: Reference SCF wavefunction from prior step
        working_dir: Working directory for output

    Returns:
        Dictionary with results
    """
    import psi4

    start_time = time.time()
    results: Dict[str, Any] = {
        "success": False,
        "error": None,
        "execution_time": 0.0,
    }

    if wfn is None:
        results["error"] = "MP2 requires a prior SCF wavefunction (ref_wfn is None)"
        results["execution_time"] = time.time() - start_time
        return results

    output_file = working_dir / "output.dat"
    psi4.core.set_output_file(str(output_file), False)

    basis = params.get("basis", wfn.basisset().name())

    try:
        mp2_energy, mp2_wfn = psi4.energy("mp2", ref_wfn=wfn, return_wfn=True)
    except Exception as e:
        results["error"] = f"MP2 calculation failed: {e}"
        results["execution_time"] = time.time() - start_time
        return results

    # Extract energies
    scf_energy = float(psi4.core.variable("SCF TOTAL ENERGY"))
    correlation_energy = float(psi4.core.variable("MP2 CORRELATION ENERGY"))

    # Collect variables
    psi4_vars = {}
    try:
        for k, v in psi4.core.variables().items():
            psi4_vars[k] = float(v) if isinstance(v, (int, float)) else str(v)
    except Exception:
        pass

    results["success"] = True
    results["energy"] = float(mp2_energy)
    results["total_energy"] = float(mp2_energy)
    results["scf_energy"] = scf_energy
    results["correlation_energy"] = correlation_energy
    results["energy_unit"] = "Hartree"
    results["method"] = "mp2"
    results["basis"] = basis
    results["psi4_variables"] = psi4_vars
    results["execution_time"] = time.time() - start_time
    results["wfn_object"] = mp2_wfn

    # Save wavefunction
    try:
        wfn_path = working_dir / "wavefunction.npy"
        mp2_wfn.to_file(str(wfn_path))
    except Exception:
        pass

    return results


def run_relax(params: Dict[str, Any], working_dir: Path) -> Dict[str, Any]:
    """
    Run Psi4 geometry optimization.

    Args:
        params: Calculation parameters
        working_dir: Working directory for output

    Returns:
        Dictionary with results including optimized geometry
    """
    import psi4

    start_time = time.time()
    results: Dict[str, Any] = {
        "success": False,
        "error": None,
        "execution_time": 0.0,
    }

    # Build molecule
    try:
        mol = build_molecule(params)
    except Exception as e:
        results["error"] = f"Failed to build molecule: {e}"
        results["execution_time"] = time.time() - start_time
        return results

    # Setup
    memory_mb = params.get("memory_mb", 500)
    nthreads = params.get("nthreads", 1)
    psi4.set_memory(f"{memory_mb} MB")
    psi4.set_num_threads(nthreads)

    output_file = working_dir / "output.dat"
    psi4.core.set_output_file(str(output_file), False)

    method = params.get("method", "scf").lower()
    basis = params.get("basis", "sto-3g")
    xc = params.get("xc", params.get("functional", None))

    # Set options
    options = {
        "basis": basis,
        "scf_type": params.get("scf_type", "df"),
    }
    if "geom_maxiter" in params:
        options["geom_maxiter"] = params["geom_maxiter"]
    psi4.set_options(options)

    # Determine method string
    if xc:
        method_str = f"{xc.lower()}/{basis}"
    else:
        method_str = f"{method}/{basis}"

    # Run optimization
    try:
        opt_energy, opt_wfn = psi4.optimize(method_str, return_wfn=True, molecule=mol)
    except Exception as e:
        results["error"] = f"Geometry optimization failed: {e}"
        results["execution_time"] = time.time() - start_time
        return results

    # Extract optimized geometry
    opt_mol = opt_wfn.molecule()
    bohr_to_ang = psi4.constants.bohr2angstroms
    geom = []
    for i in range(opt_mol.natom()):
        geom.append({
            "symbol": opt_mol.symbol(i),
            "x": opt_mol.x(i) * bohr_to_ang,
            "y": opt_mol.y(i) * bohr_to_ang,
            "z": opt_mol.z(i) * bohr_to_ang,
        })

    # Collect variables
    psi4_vars = {}
    try:
        for k, v in psi4.core.variables().items():
            psi4_vars[k] = float(v) if isinstance(v, (int, float)) else str(v)
    except Exception:
        pass

    results["success"] = True
    results["energy"] = float(opt_energy)
    results["energy_unit"] = "Hartree"
    results["converged"] = True
    results["optimized_atoms"] = geom
    results["method"] = method
    results["basis"] = basis
    results["n_atoms"] = opt_mol.natom()
    results["psi4_variables"] = psi4_vars
    results["execution_time"] = time.time() - start_time
    results["wfn_object"] = opt_wfn

    return results


def run_td(params: Dict[str, Any], wfn, working_dir: Path) -> Dict[str, Any]:
    """
    Run Psi4 TDDFT/TDA excited state calculation.

    Args:
        params: Calculation parameters
        wfn: Reference SCF wavefunction (must have save_jk=True)
        working_dir: Working directory for output

    Returns:
        Dictionary with excitation results
    """
    import psi4

    start_time = time.time()
    results: Dict[str, Any] = {
        "success": False,
        "error": None,
        "execution_time": 0.0,
    }

    if wfn is None:
        results["error"] = "TDDFT requires a prior SCF wavefunction (ref_wfn is None)"
        results["execution_time"] = time.time() - start_time
        return results

    output_file = working_dir / "output.dat"
    psi4.core.set_output_file(str(output_file), False)

    n_states = params.get("n_states", params.get("tdscf_states", 5))
    triplets = params.get("triplets", "none")
    tda = params.get("tda", params.get("tdscf_tda", True))

    try:
        from psi4.driver.procrouting.response.scf_response import tdscf_excitations
        td_res = tdscf_excitations(wfn, states=n_states, triplets=triplets, tda=tda)
    except Exception as e:
        results["error"] = f"TDDFT calculation failed: {e}"
        results["execution_time"] = time.time() - start_time
        return results

    # Parse excitations
    excitations = []
    for i, state in enumerate(td_res):
        exc_energy_au = state["EXCITATION ENERGY"]
        exc_energy_ev = exc_energy_au * 27.211386
        osc_str = state.get("LENGTH-GAUGE OSCILLATOR STRENGTH (LIN)", 0.0)
        excitations.append({
            "state": i + 1,
            "energy_au": float(exc_energy_au),
            "energy_ev": float(exc_energy_ev),
            "oscillator_strength": float(osc_str),
        })

    # Collect variables
    psi4_vars = {}
    try:
        for k, v in psi4.core.variables().items():
            psi4_vars[k] = float(v) if isinstance(v, (int, float)) else str(v)
    except Exception:
        pass

    results["success"] = True
    results["excitations"] = excitations
    results["n_states"] = n_states
    results["tda"] = tda
    results["scf_energy"] = float(psi4.core.variable("SCF TOTAL ENERGY"))
    results["psi4_variables"] = psi4_vars
    results["execution_time"] = time.time() - start_time

    return results


def run_job_chain(job_chain_path: Path) -> int:
    """
    Main entry point for chain execution from job_chain.json.

    Args:
        job_chain_path: Path to job_chain.json

    Returns:
        Exit code (0=success, 1=not converged, 2=error, 3=setup error)
    """
    try:
        job_chain = json.loads(job_chain_path.read_text())
    except Exception as e:
        print(f"ERROR: Failed to read job chain file: {e}", file=sys.stderr)
        return 3

    base_working_dir = Path(job_chain.get("base_working_dir", job_chain_path.parent))
    base_working_dir.mkdir(parents=True, exist_ok=True)

    chain_steps = job_chain.get("chain_steps", [])
    target_step_ulid = job_chain.get("target_step_ulid")

    if not chain_steps:
        _write_error_result(base_working_dir, "Chain steps list is empty")
        return 3

    if not target_step_ulid:
        _write_error_result(base_working_dir, "target_step_ulid is required")
        return 3

    # Try to import psi4
    try:
        import psi4
    except ImportError as e:
        _write_error_result(
            base_working_dir,
            f"Psi4 not installed. Install with: conda install psi4 -c conda-forge\n\nImport error: {e}",
        )
        return 2

    # Setup environment
    setup_environment(job_chain)

    # Run chain in one session
    from quantumvitas.engines.psi4.chain_execution import run_chain_session
    results = run_chain_session(
        chain_steps=chain_steps,
        base_working_dir=base_working_dir,
        target_step_ulid=target_step_ulid,
    )

    # Write results.json to target step's artifacts dir
    target_artifacts_dir = None
    for step in chain_steps:
        if step["step_ulid"] == target_step_ulid:
            target_artifacts_dir = Path(step.get("step_artifacts_dir", base_working_dir))
            break
    if target_artifacts_dir is None:
        target_artifacts_dir = base_working_dir

    results_serializable = {k: v for k, v in results.items() if k != "wfn_object"}
    target_artifacts_dir.mkdir(parents=True, exist_ok=True)
    results_file = target_artifacts_dir / "results.json"
    results_file.write_text(json.dumps(results_serializable, indent=2, default=str))

    # Also write to base working dir for compatibility
    base_results = base_working_dir / "results.json"
    base_results.write_text(json.dumps(results_serializable, indent=2, default=str))

    # Print to stdout for subprocess capture
    print(json.dumps(results_serializable, default=str))

    if results.get("success"):
        return 0
    elif results.get("error"):
        return 2
    else:
        return 1


def _write_error_result(working_dir: Path, error_msg: str) -> None:
    """Write error result to results.json and stdout."""
    results = {
        "success": False,
        "error": error_msg,
        "execution_time": 0.0,
    }
    results_file = working_dir / "results.json"
    results_file.write_text(json.dumps(results, indent=2))
    print(json.dumps(results))
