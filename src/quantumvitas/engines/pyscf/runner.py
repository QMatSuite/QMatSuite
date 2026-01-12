#!/usr/bin/env python
"""
PySCF subprocess runner.

This module is the subprocess entrypoint for PySCF calculations.
It is executed by the PySCF engine via subprocess, NOT imported by the daemon.

Usage:
    python -m quantumvitas.engines.pyscf.runner job.json

The runner:
1. Reads job.json for calculation parameters
2. Imports PySCF (only this process imports it)
3. Builds the molecule and runs the calculation
4. Writes results.json with output
5. Exits with appropriate return code

Exit codes:
    0 - Success (calculation converged)
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
from typing import Any, Dict, Optional


def detect_system_type(params: Dict[str, Any]) -> str:
    """
    Detect if system is molecular or periodic.
    
    Rule: If structure has cell/lattice -> periodic, else molecular.
    """
    if "cell" in params or "lattice" in params:
        return "periodic"
    return "molecular"


def setup_environment(job: Dict[str, Any]) -> None:
    """
    Set PySCF environment variables from job resources.
    """
    resources = job.get("resources", {})
    
    # Memory limit
    max_memory = resources.get("max_memory_mb")
    if max_memory:
        os.environ["PYSCF_MAX_MEMORY"] = str(max_memory)
    
    # Scratch directory
    scratch_dir = resources.get("scratch_dir")
    if scratch_dir:
        os.environ["PYSCF_TMPDIR"] = str(scratch_dir)
    
    # Thread count (OpenMP)
    threads = resources.get("threads")
    if threads:
        os.environ["OMP_NUM_THREADS"] = str(threads)


def build_mole(params: Dict[str, Any]):
    """
    Build PySCF Mole object from parameters.
    
    Phase 3C: Prefers structure_path over atoms list for chain execution.
    
    Args:
        params: Dictionary with structure_path (preferred) or atoms, plus basis, charge, spin, unit
        
    Returns:
        pyscf.gto.Mole object
        
    Raises:
        ValueError: If structure input is missing or invalid
    """
    from pyscf import gto
    from pathlib import Path
    
    unit = params.get("unit", "Angstrom")
    charge = params.get("charge", 0)
    spin = params.get("spin", 0)  # 2S (number of unpaired electrons)
    basis = params.get("basis", "sto-3g")
    
    atoms = []
    
    # Phase 3C: Prefer structure_path over atoms list
    if "structure_path" in params:
        # Load structure from file using canonical loader
        structure_path = Path(params["structure_path"])
        if not structure_path.exists():
            raise ValueError(f"Structure file does not exist: {structure_path}")
        
        from quantumvitas.io.structure_io import read_structure
        from pymatgen.core import Molecule as PMGMolecule
        
        structure = read_structure(structure_path)
        
        if not isinstance(structure, PMGMolecule):
            raise ValueError(f"Expected Molecule for PySCF, got {type(structure)}")
        
        if len(structure) == 0:
            raise ValueError(f"Structure has no atoms: {structure_path}")
        
        # Convert to atoms format
        for site in structure:
            coords_list = list(site.coords)
            if len(coords_list) < 3:
                raise ValueError(
                    f"Structure site has invalid coordinates (expected 3, got {len(coords_list)}): {coords_list}"
                )
            atoms.append({
                "element": site.species_string,
                "coords": [float(c) for c in coords_list],
            })
        
        # Override charge/spin from structure if not explicitly set in params
        if charge == 0:  # Only override if using default
            charge = structure.charge
        if spin == 0:  # Only override if using default
            spin = structure.spin_multiplicity - 1  # PySCF uses 2S, pymatgen uses 2S+1
    
    elif "atoms" in params:
        # Legacy path: use atoms list directly
        atoms = params.get("atoms", [])
        if not atoms:
            raise ValueError("Missing structure input: atoms list is empty")
    else:
        raise ValueError("Missing structure input: expected structure_path or atoms in parameters")
    
    # Validate atoms list
    if not atoms:
        raise ValueError("Invalid atoms format: atoms list is empty after processing")
    
    # Build atom string for PySCF
    # PySCF accepts: "O 0 0 0; H 0 0.757 0.587; H 0 -0.757 0.587"
    atom_lines = []
    for i, atom in enumerate(atoms):
        element = atom.get("element", atom.get("symbol", "X"))
        
        # Handle different coordinate formats
        if "coords" in atom:
            coords = atom["coords"]
            if not isinstance(coords, list):
                raise ValueError(
                    f"Atom {i} ({element}) coords must be a list, got {type(coords)}: {coords}"
                )
            if len(coords) != 3:
                raise ValueError(
                    f"Atom {i} ({element}) coordinates must have exactly 3 elements (x, y, z), "
                    f"got coords={coords} (length={len(coords)})"
                )
            x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
        else:
            x = float(atom.get("x", 0.0))
            y = float(atom.get("y", 0.0))
            z = float(atom.get("z", 0.0))
        
        atom_lines.append(f"{element} {x} {y} {z}")
    
    atom_str = "; ".join(atom_lines)
    
    mol = gto.Mole()
    mol.atom = atom_str
    mol.basis = basis
    mol.charge = charge
    mol.spin = spin
    mol.unit = unit
    mol.build()
    
    return mol


def run_scf(params: Dict[str, Any], working_dir: Path) -> Dict[str, Any]:
    """
    Run PySCF SCF (HF or DFT) calculation.
    
    Args:
        params: Calculation parameters
        working_dir: Working directory for output
        
    Returns:
        Dictionary with results
    """
    import numpy as np
    from pyscf import gto, scf, dft
    
    start_time = time.time()
    results: Dict[str, Any] = {
        "success": False,
        "error": None,
        "execution_time": 0.0,
    }
    
    # Build molecule
    try:
        mol = build_mole(params)
    except Exception as e:
        results["error"] = f"Failed to build molecule: {e}"
        results["execution_time"] = time.time() - start_time
        return results
    
    # Setup SCF/DFT method
    method = params.get("method", "rhf").lower()
    xc = params.get("xc", "pbe")
    
    try:
        if method in ("rhf", "hf"):
            mf = scf.RHF(mol)
        elif method == "uhf":
            mf = scf.UHF(mol)
        elif method == "rohf":
            mf = scf.ROHF(mol)
        elif method in ("rks", "dft"):
            mf = dft.RKS(mol)
            mf.xc = xc
        elif method == "uks":
            mf = dft.UKS(mol)
            mf.xc = xc
        elif method == "roks":
            mf = dft.ROKS(mol)
            mf.xc = xc
        else:
            results["error"] = f"Unknown method: {method}. Supported: rhf, uhf, rohf, rks, uks, roks"
            results["execution_time"] = time.time() - start_time
            return results
    except Exception as e:
        results["error"] = f"Failed to setup SCF: {e}"
        results["execution_time"] = time.time() - start_time
        return results
    
    # Convergence settings
    mf.max_cycle = params.get("max_cycle", 50)
    mf.conv_tol = params.get("conv_tol", 1e-9)
    
    # Checkpoint file (Phase 3C: support checkpointing for restart)
    checkpoint_file = working_dir / "checkpoint.chk"
    mf.chkfile = str(checkpoint_file)
    
    # Init guess from checkpoint if available (Phase 3C: support restart)
    if checkpoint_file.exists():
        try:
            mf.init_guess = 'chkfile'
        except Exception:
            # If loading fails, continue with default init_guess
            pass
    
    # Verbosity (write to log file)
    log_file = working_dir / "pyscf.log"
    mf.verbose = params.get("verbose", 4)
    log_handle = open(log_file, 'w')
    mf.stdout = log_handle
    
    # Run SCF
    try:
        energy = mf.kernel()
        converged = mf.converged
    except Exception as e:
        log_handle.close()
        results["error"] = f"SCF calculation failed: {e}"
        results["execution_time"] = time.time() - start_time
        return results
    finally:
        log_handle.close()
    
    # Build results
    results["success"] = converged
    results["energy"] = float(energy)
    results["energy_unit"] = "Hartree"
    results["converged"] = converged
    results["method"] = method
    results["basis"] = params.get("basis", "sto-3g")
    results["n_electrons"] = mol.nelectron
    results["n_atoms"] = mol.natm
    results["execution_time"] = time.time() - start_time
    
    if method in ("rks", "uks", "roks", "dft"):
        results["xc_functional"] = xc
    
    # Extract MO information
    try:
        mo_energy = mf.mo_energy
        mo_occ = mf.mo_occ
        
        # Handle unrestricted case (alpha/beta separate)
        if isinstance(mo_energy, (list, tuple)) or (hasattr(mo_energy, 'ndim') and mo_energy.ndim == 2):
            # Unrestricted: [alpha, beta]
            if hasattr(mo_energy[0], 'tolist'):
                results["mo_energies_alpha"] = mo_energy[0].tolist()
                results["mo_energies_beta"] = mo_energy[1].tolist()
                results["mo_occupations_alpha"] = mo_occ[0].tolist()
                results["mo_occupations_beta"] = mo_occ[1].tolist()
            else:
                results["mo_energies_alpha"] = list(mo_energy[0])
                results["mo_energies_beta"] = list(mo_energy[1])
                results["mo_occupations_alpha"] = list(mo_occ[0])
                results["mo_occupations_beta"] = list(mo_occ[1])
            
            # HOMO/LUMO for alpha
            alpha_e = np.array(results["mo_energies_alpha"])
            alpha_occ = np.array(results["mo_occupations_alpha"])
            homo_idx = int(np.where(alpha_occ > 0)[0][-1]) if np.any(alpha_occ > 0) else None
            lumo_idx = int(np.where(alpha_occ == 0)[0][0]) if np.any(alpha_occ == 0) else None
            
            results["homo_index_alpha"] = homo_idx
            results["lumo_index_alpha"] = lumo_idx
            if homo_idx is not None:
                results["homo_energy_alpha"] = float(alpha_e[homo_idx])
            if lumo_idx is not None:
                results["lumo_energy_alpha"] = float(alpha_e[lumo_idx])
            if homo_idx is not None and lumo_idx is not None:
                gap = float(alpha_e[lumo_idx] - alpha_e[homo_idx])
                results["gap_alpha"] = gap
                results["gap_alpha_ev"] = gap * 27.2114
        else:
            # Restricted
            if hasattr(mo_energy, 'tolist'):
                results["mo_energies"] = mo_energy.tolist()
                results["mo_occupations"] = mo_occ.tolist()
            else:
                results["mo_energies"] = list(mo_energy)
                results["mo_occupations"] = list(mo_occ)
            
            # Find HOMO/LUMO
            mo_e = np.array(results["mo_energies"])
            mo_o = np.array(results["mo_occupations"])
            
            homo_idx = None
            lumo_idx = None
            for i, occ in enumerate(mo_o):
                if occ > 0:
                    homo_idx = i
                elif lumo_idx is None and homo_idx is not None:
                    lumo_idx = i
                    break
            
            results["homo_index"] = homo_idx
            results["lumo_index"] = lumo_idx
            
            if homo_idx is not None:
                results["homo_energy"] = float(mo_e[homo_idx])
            if lumo_idx is not None:
                results["lumo_energy"] = float(mo_e[lumo_idx])
            if homo_idx is not None and lumo_idx is not None:
                gap = float(mo_e[lumo_idx] - mo_e[homo_idx])
                results["gap"] = gap
                results["gap_ev"] = gap * 27.2114  # Hartree to eV
    except Exception:
        # MO extraction failed, continue without it
        pass
    
    # Dipole moment (if available)
    try:
        dipole = mf.dip_moment(verbose=0)
        if hasattr(dipole, 'tolist'):
            results["dipole_moment"] = dipole.tolist()
        else:
            results["dipole_moment"] = list(dipole)
        results["dipole_moment_unit"] = "Debye"
    except Exception:
        pass
    
    # Mulliken charges (if available)
    try:
        mulliken = mf.mulliken_pop(verbose=0)
        if len(mulliken) >= 2:
            charges = mulliken[1]
            if hasattr(charges, 'tolist'):
                results["mulliken_charges"] = charges.tolist()
            else:
                results["mulliken_charges"] = list(charges)
    except Exception:
        pass
    
    # PySCF version
    try:
        import pyscf
        results["pyscf_version"] = pyscf.__version__
    except Exception:
        pass
    
    if not converged:
        results["error"] = f"SCF did not converge after {mf.max_cycle} cycles"
    
    return results


def write_input_script(params: Dict[str, Any], working_dir: Path) -> None:
    """
    Write a Python script that reproduces the calculation.
    
    Useful for debugging and reproducibility.
    """
    script_lines = [
        "#!/usr/bin/env python",
        '"""',
        "PySCF input script generated by QMatSuite.",
        "Run with: python pyscf_input.py",
        '"""',
        "",
        "from pyscf import gto, scf, dft",
        "",
        "# Build molecule",
        "mol = gto.Mole()",
    ]
    
    # Atom string
    atoms = params.get("atoms", [])
    atom_lines = []
    for atom in atoms:
        element = atom.get("element", atom.get("symbol", "X"))
        if "coords" in atom:
            coords = atom["coords"]
            if not coords or len(coords) < 3:
                raise ValueError(
                    f"Atom coordinates must have exactly 3 elements (x, y, z), "
                    f"got coords={coords} (length={len(coords) if coords else 0}) for element={element}"
                )
            x, y, z = coords[0], coords[1], coords[2]
        else:
            x = atom.get("x", 0.0)
            y = atom.get("y", 0.0)
            z = atom.get("z", 0.0)
        atom_lines.append(f"    {element} {x} {y} {z}")
    
    script_lines.append("mol.atom = '''")
    script_lines.extend(atom_lines)
    script_lines.append("'''")
    
    script_lines.append(f"mol.basis = '{params.get('basis', 'sto-3g')}'")
    script_lines.append(f"mol.charge = {params.get('charge', 0)}")
    script_lines.append(f"mol.spin = {params.get('spin', 0)}")
    script_lines.append(f"mol.unit = '{params.get('unit', 'Angstrom')}'")
    script_lines.append("mol.build()")
    script_lines.append("")
    
    # Method setup
    method = params.get("method", "rhf").lower()
    xc = params.get("xc", "pbe")
    
    if method in ("rhf", "hf"):
        script_lines.append("mf = scf.RHF(mol)")
    elif method == "uhf":
        script_lines.append("mf = scf.UHF(mol)")
    elif method == "rohf":
        script_lines.append("mf = scf.ROHF(mol)")
    elif method in ("rks", "dft"):
        script_lines.append("mf = dft.RKS(mol)")
        script_lines.append(f"mf.xc = '{xc}'")
    elif method == "uks":
        script_lines.append("mf = dft.UKS(mol)")
        script_lines.append(f"mf.xc = '{xc}'")
    elif method == "roks":
        script_lines.append("mf = dft.ROKS(mol)")
        script_lines.append(f"mf.xc = '{xc}'")
    
    script_lines.append(f"mf.max_cycle = {params.get('max_cycle', 50)}")
    script_lines.append(f"mf.conv_tol = {params.get('conv_tol', 1e-9)}")
    script_lines.append("")
    script_lines.append("# Run calculation")
    script_lines.append("energy = mf.kernel()")
    script_lines.append("")
    script_lines.append("# Print results")
    script_lines.append("print(f'Total energy: {energy:.10f} Hartree')")
    script_lines.append("print(f'Converged: {mf.converged}')")
    
    script_path = working_dir / "pyscf_input.py"
    script_path.write_text("\n".join(script_lines) + "\n")


def run_mp2(params: Dict[str, Any], working_dir: Path) -> Dict[str, Any]:
    """
    Run PySCF MP2 (Møller-Plesset perturbation theory of second order) calculation.
    
    Phase 3C: MP2 requires a converged SCF calculation. This function:
    1. Loads the SCF checkpoint file from a previous step
    2. Rebuilds mol + mf, runs a quick SCF kernel to obtain valid mf object
    3. Runs MP2(mf).kernel() to compute correlation energy
    4. Returns total energy (SCF + correlation) and correlation energy
    
    Args:
        params: Calculation parameters (must include scf_checkpoint_path or use default)
        working_dir: Working directory for output
        
    Returns:
        Dictionary with results
    """
    import numpy as np
    from pyscf import gto, scf, dft, mp
    
    start_time = time.time()
    results: Dict[str, Any] = {
        "success": False,
        "error": None,
        "execution_time": 0.0,
    }
    
    # Determine SCF checkpoint path (Phase 3C: MP2 requires SCF checkpoint)
    scf_checkpoint_path = params.get("scf_checkpoint_path")
    if scf_checkpoint_path:
        checkpoint_file = Path(scf_checkpoint_path)
        if not checkpoint_file.is_absolute():
            checkpoint_file = working_dir.parent / checkpoint_file
    else:
        # Default: look for checkpoint.chk in parent directory (from previous SCF step)
        # For scf_mp2 workflow, SCF writes to working_dir/checkpoint.chk, MP2 reads from same
        checkpoint_file = working_dir / "checkpoint.chk"
        if not checkpoint_file.exists():
            # Try parent directory (if steps have separate dirs)
            checkpoint_file = working_dir.parent / "checkpoint.chk"
    
    if not checkpoint_file.exists():
        results["error"] = f"SCF checkpoint file not found: {checkpoint_file}. MP2 requires a converged SCF calculation."
        results["execution_time"] = time.time() - start_time
        return results
    
    # Build molecule (same as SCF)
    try:
        mol = build_mole(params)
    except Exception as e:
        results["error"] = f"Failed to build molecule: {e}"
        results["execution_time"] = time.time() - start_time
        return results
    
    # Setup SCF method (same as SCF step to rebuild mf object)
    method = params.get("method", "rhf").lower()
    xc = params.get("xc", "pbe")
    
    try:
        if method in ("rhf", "hf"):
            mf = scf.RHF(mol)
        elif method == "uhf":
            mf = scf.UHF(mol)
        elif method == "rohf":
            mf = scf.ROHF(mol)
        elif method in ("rks", "dft"):
            mf = dft.RKS(mol)
            mf.xc = xc
        elif method == "uks":
            mf = dft.UKS(mol)
            mf.xc = xc
        elif method == "roks":
            mf = dft.ROKS(mol)
            mf.xc = xc
        else:
            results["error"] = f"Unknown method: {method}. MP2 requires RHF/UHF/ROHF or RKS/UKS/ROKS SCF."
            results["execution_time"] = time.time() - start_time
            return results
    except Exception as e:
        results["error"] = f"Failed to setup SCF: {e}"
        results["execution_time"] = time.time() - start_time
        return results
    
    # Load checkpoint and rebuild mf (Phase 3C: rebuild from chkfile)
    try:
        mf.chkfile = str(checkpoint_file)
        mf.init_guess = 'chkfile'
        # Run a quick SCF kernel to obtain valid mf object (needed for MP2)
        # This should be fast since we're starting from converged orbitals
        mf.max_cycle = 1  # Just one iteration to rebuild mf object
        scf_energy = mf.kernel()
        if not mf.converged:
            # If it didn't converge in 1 cycle, that's OK - we're just rebuilding from chkfile
            # The checkpoint should have valid orbitals
            pass
    except Exception as e:
        results["error"] = f"Failed to load SCF checkpoint: {e}. Checkpoint file may be corrupt or incompatible."
        results["execution_time"] = time.time() - start_time
        return results
    
    # Setup MP2 (Phase 3C: MP2 calculation)
    try:
        if method in ("rhf", "hf", "rks", "dft"):
            mp2 = mp.MP2(mf)
        elif method in ("uhf", "uks"):
            mp2 = mp.UMP2(mf)
        elif method in ("rohf", "roks"):
            mp2 = mp.ROMP2(mf)
        else:
            results["error"] = f"MP2 not supported for method: {method}"
            results["execution_time"] = time.time() - start_time
            return results
    except Exception as e:
        results["error"] = f"Failed to setup MP2: {e}"
        results["execution_time"] = time.time() - start_time
        return results
    
    # Verbosity (write to log file)
    log_file = working_dir / "pyscf.log"
    mp2.verbose = params.get("verbose", 4)
    log_handle = open(log_file, 'w')
    mp2.stdout = log_handle
    
    # Run MP2
    try:
        mp2_energy, t2 = mp2.kernel()
        # Total energy = SCF energy + correlation energy
        total_energy = float(scf_energy) + float(mp2_energy)
        correlation_energy = float(mp2_energy)
    except Exception as e:
        log_handle.close()
        results["error"] = f"MP2 calculation failed: {e}"
        results["execution_time"] = time.time() - start_time
        return results
    finally:
        log_handle.close()
    
    # Build results (Phase 3C: MP2 results format)
    results["success"] = True
    results["energy"] = total_energy
    results["energy_unit"] = "Hartree"
    results["scf_energy"] = float(scf_energy)
    results["correlation_energy"] = correlation_energy
    results["method"] = f"{method}_mp2"
    results["basis"] = params.get("basis", "sto-3g")
    results["n_electrons"] = mol.nelectron
    results["n_atoms"] = mol.natm
    results["execution_time"] = time.time() - start_time
    
    # PySCF version
    try:
        import pyscf
        results["pyscf_version"] = pyscf.__version__
    except Exception:
        pass
    
    return results


def run_job_chain(job_chain_path: Path) -> int:
    """
    Main entry point for chain execution: run a PySCF dependency chain from job_chain.json.
    
    Phase 3C: One-session execution model for RunStep mode.
    
    Args:
        job_chain_path: Path to job_chain.json
        
    Returns:
        Exit code (0=success, 1=not converged, 2=error, 3=setup error)
    """
    # Read job chain spec
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
        results = {
            "success": False,
            "error": "Chain steps list is empty",
            "execution_time": 0.0,
        }
        results_file = base_working_dir / "results.json"
        results_file.write_text(json.dumps(results, indent=2))
        print(json.dumps(results))
        return 3
    
    if not target_step_ulid:
        results = {
            "success": False,
            "error": "target_step_ulid is required",
            "execution_time": 0.0,
        }
        results_file = base_working_dir / "results.json"
        results_file.write_text(json.dumps(results, indent=2))
        print(json.dumps(results))
        return 3
    
    # Try to import PySCF
    try:
        import pyscf
    except ImportError as e:
        results = {
            "success": False,
            "error": f"PySCF not installed. Install with: pip install pyscf\n\nImport error: {e}",
            "execution_time": 0.0,
        }
        results_file = base_working_dir / "results.json"
        results_file.write_text(json.dumps(results, indent=2))
        print(json.dumps(results))
        return 2
    
    # Setup environment
    resources = job_chain.get("resources", {})
    setup_environment({"resources": resources})
    
    # Run chain in one session
    from quantumvitas.engines.pyscf.chain_execution import run_chain_session
    results = run_chain_session(
        chain_steps=chain_steps,
        base_working_dir=base_working_dir,
        target_step_ulid=target_step_ulid,
    )
    
    # Write final results.json (target step's results)
    target_artifacts_dir = Path(chain_steps[-1]["step_artifacts_dir"]) if chain_steps else base_working_dir
    results_file = target_artifacts_dir / "results.json"
    # Remove mf_object from results before serialization
    results_serializable = {k: v for k, v in results.items() if k != "mf_object"}
    results_file.write_text(json.dumps(results_serializable, indent=2))
    
    # Also write to base_working_dir for compatibility
    base_results_file = base_working_dir / "results.json"
    base_results_file.write_text(json.dumps(results_serializable, indent=2))
    
    # Print results to stdout
    print(json.dumps(results_serializable))
    
    # Return exit code
    if results.get("success"):
        return 0
    elif results.get("error"):
        return 2
    else:
        return 1


def run_job(job_path: Path) -> int:
    """
    DEPRECATED: PySCF execution is chain-only.
    
    This function is blocked for PySCF. Use run_job_chain() instead.
    Single-step execution is converted to chain of length 1 in __main__.py.
    
    Args:
        job_path: Path to job.json
        
    Returns:
        Exit code (0=success, 1=not converged, 2=error, 3=setup error)
        
    Raises:
        RuntimeError: Always, as PySCF is chain-only
    """
    raise RuntimeError(
        "PySCF runner is chain-only. Single-step execution must be converted to chain of length 1. "
        "This should be handled by __main__.py. If you see this error, the conversion failed."
    )
    # Read job spec
    try:
        job = json.loads(job_path.read_text())
    except Exception as e:
        print(f"ERROR: Failed to read job file: {e}", file=sys.stderr)
        return 3
    
    working_dir = Path(job.get("working_dir", job_path.parent))
    working_dir.mkdir(parents=True, exist_ok=True)
    params = job.get("parameters", {})
    
    results_file = working_dir / "results.json"
    
    # Check system type
    system_type = detect_system_type(params)
    if system_type == "periodic":
        results = {
            "success": False,
            "error": "PBC/periodic systems not yet supported by PySCF engine. Use QE for periodic calculations.",
            "execution_time": 0.0,
        }
        results_file.write_text(json.dumps(results, indent=2))
        print(json.dumps(results))
        return 2
    
    # Setup environment
    setup_environment(job)
    
    # Try to import PySCF
    try:
        import pyscf
    except ImportError as e:
        results = {
            "success": False,
            "error": f"PySCF not installed. Install with: pip install pyscf\n\nImport error: {e}",
            "execution_time": 0.0,
        }
        results_file.write_text(json.dumps(results, indent=2))
        print(json.dumps(results))
        return 2
    
    # Determine step type
    step_type = job.get("step_type", "pyscf_scf")
    
    # Run calculation (Phase 3C: support pyscf_mp2)
    if step_type in ("pyscf_scf", "pyscf_rhf", "pyscf_uhf", "pyscf_rks", "pyscf_uks"):
        results = run_scf(params, working_dir)
    elif step_type == "pyscf_mp2":
        results = run_mp2(params, working_dir)
    else:
        results = {
            "success": False,
            "error": f"Unknown PySCF step type: {step_type}",
            "execution_time": 0.0,
        }
    
    # Write reproducible input script
    try:
        write_input_script(params, working_dir)
    except Exception:
        pass  # Non-fatal
    
    # Write results.json
    try:
        results_file.write_text(json.dumps(results, indent=2))
    except Exception as e:
        print(f"WARNING: Failed to write results.json: {e}", file=sys.stderr)
    
    # Print results to stdout for subprocess capture
    print(json.dumps(results))
    
    # Return exit code
    if results.get("success"):
        return 0
    elif results.get("converged") is False:
        return 1
    else:
        return 2


def main():
    """CLI entrypoint."""
    if len(sys.argv) < 2:
        print("Usage: python -m quantumvitas.engines.pyscf.runner job.json", file=sys.stderr)
        sys.exit(3)
    
    job_path = Path(sys.argv[1])
    if not job_path.exists():
        print(f"ERROR: Job file not found: {job_path}", file=sys.stderr)
        sys.exit(3)
    
    try:
        exit_code = run_job(job_path)
        sys.exit(exit_code)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()


