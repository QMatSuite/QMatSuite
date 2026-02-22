"""
PySCF chain execution for one-session dependency chain runs.

Phase 3C: Implements one-session execution of dependency chains.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import PySCF once (will be imported when this module is loaded)
try:
    import pyscf
    PYSCF_AVAILABLE = True
except ImportError:
    PYSCF_AVAILABLE = False


def run_chain_session(
    chain_steps: List[Dict[str, Any]],
    base_working_dir: Path,
    target_step_ulid: str,
) -> Dict[str, Any]:
    """
    Execute a dependency chain in one PySCF session.
    
    Phase 3C: One-session execution model. Import PySCF once, execute steps sequentially,
    maintain in-memory objects (mol, mf) between steps.
    
    Args:
        chain_steps: List of step specs in order (from root to target)
                    Each spec has: step_ulid, step_type, parameters, step_artifacts_dir
        base_working_dir: Base working directory (for relative paths)
        target_step_ulid: ULID of the target step (always full rerun)
        
    Returns:
        Dict with results for the target step (last step in chain)
    """
    if not PYSCF_AVAILABLE:
        return {
            "success": False,
            "error": "PySCF not installed. Install with: pip install pyscf",
            "execution_time": 0.0,
        }
    
    from pyscf import gto, scf, dft, mp
    
    start_time = time.time()
    results: Dict[str, Any] = {
        "success": False,
        "error": None,
        "execution_time": 0.0,
    }
    
    # State storage: maintain objects keyed by state type
    state_objects: Dict[str, Any] = {}  # e.g., {"mf": mf_object}
    
    # Execute each step in the chain sequentially
    for step_idx, step_spec in enumerate(chain_steps):
        step_ulid = step_spec["step_ulid"]
        step_type = step_spec.get("step_type_spec")
        params = step_spec["parameters"]
        step_artifacts_dir = Path(step_spec.get("step_artifacts_dir", base_working_dir))
        is_target_step = (step_ulid == target_step_ulid)
        
        # Clear step artifacts directory before execution
        if step_artifacts_dir.exists():
            import shutil
            for item in step_artifacts_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        step_artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if step_type in ("pyscf_scf", "pyscf_rhf", "pyscf_uhf", "pyscf_rks", "pyscf_uks"):
                # SCF step
                # Phase 3C: Target SCF step must NOT use chkfile init_guess (always full rerun)
                allow_chkfile_init_guess = not is_target_step and step_spec.get("allow_chkfile_init_guess", True)
                
                step_result = _run_scf_in_session(
                    params=params,
                    working_dir=step_artifacts_dir,
                    allow_chkfile_init_guess=allow_chkfile_init_guess,
                )
                
                if not step_result["success"]:
                    results["error"] = f"SCF step ({step_ulid}) failed: {step_result.get('error', 'Unknown error')}"
                    results["execution_time"] = time.time() - start_time
                    return results
                
                # Store mf object in state
                state_objects["mf"] = step_result["mf_object"]
                results = step_result  # Last step's result is the final result
                
            elif step_type == "pyscf_mp2":
                # MP2 step: requires mf from state
                if "mf" not in state_objects:
                    results["error"] = "MP2 step requires SCF mf object, but not found in chain state"
                    results["execution_time"] = time.time() - start_time
                    return results
                
                mf = state_objects["mf"]
                step_result = _run_mp2_in_session(
                    params=params,
                    mf=mf,
                    working_dir=step_artifacts_dir,
                )
                
                if not step_result["success"]:
                    results["error"] = f"MP2 step ({step_ulid}) failed: {step_result.get('error', 'Unknown error')}"
                    results["execution_time"] = time.time() - start_time
                    return results
                
                results = step_result  # Last step's result is the final result
                
            elif step_type == "pyscf_relax":
                # Relax step: geometry optimization
                # Relax steps are standalone (no dependencies on mf from state)
                # They require structure_path in params
                from qmatsuite.engines.pyscf.runner import run_pyscf_relax
                
                step_result = run_pyscf_relax(
                    params=params,
                    working_dir=step_artifacts_dir,
                )
                
                if not step_result["success"]:
                    results["error"] = f"Relax step ({step_ulid}) failed: {step_result.get('error', 'Unknown error')}"
                    results["execution_time"] = time.time() - start_time
                    return results
                
                results = step_result  # Last step's result is the final result
                
            else:
                results["error"] = f"Unknown step type in chain: {step_type}"
                results["execution_time"] = time.time() - start_time
                return results
                
        except Exception as e:
            import traceback
            error_msg = f"Step {step_ulid} ({step_type}) failed: {str(e)}"
            traceback_str = traceback.format_exc()
            results["error"] = f"{error_msg}\n{traceback_str}"
            results["execution_time"] = time.time() - start_time
            return results
    
    results["execution_time"] = time.time() - start_time
    return results


def _run_scf_in_session(
    params: Dict[str, Any],
    working_dir: Path,
    allow_chkfile_init_guess: bool = True,
) -> Dict[str, Any]:
    """
    Run SCF calculation in session (returns mf object for state storage).
    
    Internal helper for chain execution.
    """
    from pyscf import gto, scf, dft
    
    # Build molecule
    from qmatsuite.engines.pyscf.runner import build_mole
    try:
        mol = build_mole(params)
    except Exception as e:
        import traceback
        error_msg = f"Failed to build molecule: {e}"
        traceback_str = traceback.format_exc()
        return {
            "success": False,
            "error": f"{error_msg}\n{traceback_str}",
            "execution_time": 0.0,
        }
    
    # Setup SCF/DFT method
    method = params.get("method", "rhf").lower()
    xc = params.get("xc", "pbe")
    
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
        return {
            "success": False,
            "error": f"Unknown method: {method}",
            "execution_time": 0.0,
        }
    
    # Convergence settings
    mf.max_cycle = params.get("max_cycle", 50)
    mf.conv_tol = params.get("conv_tol", 1e-9)
    
    # Checkpoint file
    checkpoint_file = working_dir / "checkpoint.chk"
    mf.chkfile = str(checkpoint_file)
    
    # Fix #3: Create pyscf.log file (PySCF stdout/stderr)
    log_file = working_dir / "pyscf.log"
    mf.verbose = params.get("verbose", 4)
    log_handle = open(log_file, 'w')
    mf.stdout = log_handle
    
    # Init guess from checkpoint if available and allowed
    if allow_chkfile_init_guess and checkpoint_file.exists():
        try:
            mf.init_guess = 'chkfile'
        except Exception:
            pass
    
    # Run SCF
    try:
        energy = mf.kernel()
        converged = mf.converged
        log_handle.close()
    except Exception as e:
        log_handle.close()
        return {
            "success": False,
            "error": f"SCF calculation failed: {e}",
            "execution_time": 0.0,
        }
    
    # Build results
    result = {
        "success": converged,
        "energy": float(energy),
        "energy_unit": "Hartree",
        "converged": converged,
        "method": method,
        "basis": params.get("basis", "sto-3g"),
        "n_electrons": mol.nelectron,
        "n_atoms": mol.natm,
        "mf_object": mf,  # Store mf object for state
    }
    
    if method in ("rks", "uks", "roks", "dft"):
        result["xc_functional"] = xc
    
    # Extract MO information
    try:
        mo_energy = mf.mo_energy
        mo_occ = mf.mo_occ
        
        if isinstance(mo_energy, (list, tuple)) or (hasattr(mo_energy, 'ndim') and mo_energy.ndim == 2):
            # Unrestricted case
            mo_energy_alpha = mo_energy[0] if isinstance(mo_energy, (list, tuple)) else mo_energy[0]
            mo_energy_beta = mo_energy[1] if isinstance(mo_energy, (list, tuple)) else mo_energy[1]
            mo_occ_alpha = mo_occ[0] if isinstance(mo_occ, (list, tuple)) else mo_occ[0]
            mo_occ_beta = mo_occ[1] if isinstance(mo_occ, (list, tuple)) else mo_occ[1]
            
            # Fix #4: Add mo_energies_alpha and mo_energies_beta to results
            if hasattr(mo_energy_alpha, 'tolist'):
                result["mo_energies_alpha"] = mo_energy_alpha.tolist()
            else:
                result["mo_energies_alpha"] = list(mo_energy_alpha)
            if hasattr(mo_energy_beta, 'tolist'):
                result["mo_energies_beta"] = mo_energy_beta.tolist()
            else:
                result["mo_energies_beta"] = list(mo_energy_beta)
            
            homo_alpha_idx = int(sum(mo_occ_alpha > 0.5)) - 1
            lumo_alpha_idx = homo_alpha_idx + 1
            homo_beta_idx = int(sum(mo_occ_beta > 0.5)) - 1
            lumo_beta_idx = homo_beta_idx + 1
            
            homo_alpha = float(mo_energy_alpha[homo_alpha_idx]) if homo_alpha_idx >= 0 else None
            lumo_alpha = float(mo_energy_alpha[lumo_alpha_idx]) if lumo_alpha_idx < len(mo_energy_alpha) else None
            homo_beta = float(mo_energy_beta[homo_beta_idx]) if homo_beta_idx >= 0 else None
            lumo_beta = float(mo_energy_beta[lumo_beta_idx]) if lumo_beta_idx < len(mo_energy_beta) else None
            
            gap_alpha = (lumo_alpha - homo_alpha) if (homo_alpha is not None and lumo_alpha is not None) else None
            gap_beta = (lumo_beta - homo_beta) if (homo_beta is not None and lumo_beta is not None) else None
            
            result["homo_alpha"] = homo_alpha
            result["lumo_alpha"] = lumo_alpha
            result["gap_alpha"] = gap_alpha
            result["homo_beta"] = homo_beta
            result["lumo_beta"] = lumo_beta
            result["gap_beta"] = gap_beta
            result["gap"] = min(gap_alpha, gap_beta) if (gap_alpha is not None and gap_beta is not None) else (gap_alpha or gap_beta)
        else:
            # Restricted case
            homo_idx = int(sum(mo_occ > 0.5)) - 1
            lumo_idx = homo_idx + 1 if homo_idx + 1 < len(mo_energy) else None
            homo = float(mo_energy[homo_idx]) if homo_idx >= 0 else None
            lumo = float(mo_energy[lumo_idx]) if lumo_idx is not None and lumo_idx < len(mo_energy) else None
            gap = (lumo - homo) if (homo is not None and lumo is not None) else None
            
            # Fix #2: Add homo_index and lumo_index to results
            result["homo_index"] = homo_idx if homo_idx >= 0 else None
            result["lumo_index"] = lumo_idx
            
            result["homo"] = homo
            result["lumo"] = lumo
            result["gap"] = gap
    except Exception:
        pass  # MO info extraction is optional
    
    # Write results.json
    results_json = {k: v for k, v in result.items() if k != "mf_object"}  # Don't serialize mf object
    results_file = working_dir / "results.json"
    results_file.write_text(json.dumps(results_json, indent=2))
    
    # Write input script for reproducibility
    try:
        from qmatsuite.engines.pyscf.runner import write_input_script
        write_input_script(params, working_dir)
    except Exception:
        pass  # Input script generation is optional
    
    # Write checkpoint
    try:
        mf.chkfile = str(checkpoint_file)
        # Checkpoint is saved automatically by PySCF when mf.chkfile is set and kernel() runs
    except Exception:
        pass
    
    return result


def _run_mp2_in_session(
    params: Dict[str, Any],
    mf: Any,  # PySCF mean-field object
    working_dir: Path,
) -> Dict[str, Any]:
    """
    Run MP2 calculation in session (uses mf object from state).
    
    Internal helper for chain execution.
    """
    from pyscf import mp
    
    start_time = time.time()
    
    try:
        # Run MP2
        mp2_calc = mp.MP2(mf)
        mp2_energy, mp2_corr = mp2_calc.kernel()

        scf_energy = float(mf.e_tot)

        # Extract correlation energy robustly (handle numpy arrays/scalars)
        # PySCF versions may return different types
        import numpy as np
        if isinstance(mp2_corr, np.ndarray):
            # Array case: extract scalar value
            if mp2_corr.size == 1:
                correlation_energy = float(mp2_corr.item())
            else:
                # Multi-element array: take first element
                correlation_energy = float(mp2_corr.flat[0])
        elif hasattr(mp2_corr, '__iter__') and not isinstance(mp2_corr, str):
            # List/tuple case
            correlation_energy = float(mp2_corr[0] if len(mp2_corr) > 0 else 0.0)
        else:
            # Scalar case (int/float)
            correlation_energy = float(mp2_corr)

        total_energy = scf_energy + correlation_energy
        
        result = {
            "success": True,
            "total_energy": total_energy,
            "scf_energy": scf_energy,
            "correlation_energy": correlation_energy,
            "method": "mp2",
            "basis": params.get("basis", "sto-3g"),
            "n_electrons": mf.mol.nelectron,
            "n_atoms": mf.mol.natm,
            "execution_time": time.time() - start_time,
        }
        
        # Write results.json
        results_file = working_dir / "results.json"
        results_file.write_text(json.dumps(result, indent=2))
        
        return result
        
    except Exception as e:
        import traceback
        error_msg = f"MP2 calculation failed: {e}"
        traceback_str = traceback.format_exc()
        return {
            "success": False,
            "error": f"{error_msg}\n{traceback_str}",
            "execution_time": time.time() - start_time,
        }

