"""
Psi4 chain execution for one-session dependency chain runs.

Maintains wavefunction state between steps via ref_wfn parameter.
Unlike PySCF which uses checkpoint files, Psi4 keeps the wavefunction
object in memory within the subprocess session.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

try:
    import psi4
    PSI4_AVAILABLE = True
except ImportError:
    PSI4_AVAILABLE = False


def run_chain_session(
    chain_steps: List[Dict[str, Any]],
    base_working_dir: Path,
    target_step_ulid: str,
) -> Dict[str, Any]:
    """
    Execute a dependency chain in one Psi4 session.

    Import psi4 once, execute steps sequentially, maintain wavefunction
    state between steps via ref_wfn.

    Args:
        chain_steps: List of step specs in dependency order (root to target).
                    Each spec has: step_ulid, step_type_spec, parameters, step_artifacts_dir
        base_working_dir: Base working directory
        target_step_ulid: ULID of the target step

    Returns:
        Dict with results for the target step
    """
    if not PSI4_AVAILABLE:
        return {
            "success": False,
            "error": "Psi4 not installed. Install with: conda install psi4 -c conda-forge",
            "execution_time": 0.0,
        }

    start_time = time.time()
    results: Dict[str, Any] = {
        "success": False,
        "error": None,
        "execution_time": 0.0,
    }

    # State storage: wavefunction passed between steps
    state_objects: Dict[str, Any] = {}  # {"wfn": psi4.core.Wavefunction}

    for step_idx, step_spec in enumerate(chain_steps):
        step_ulid = step_spec["step_ulid"]
        step_type = step_spec.get("step_type_spec", "")
        params = step_spec["parameters"]
        step_artifacts_dir = Path(step_spec.get("step_artifacts_dir", base_working_dir))
        is_target_step = (step_ulid == target_step_ulid)

        # Clear and create step artifacts directory
        if step_artifacts_dir.exists():
            import shutil
            for item in step_artifacts_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        step_artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Clean psi4 global state between steps
        psi4.core.clean()
        psi4.core.clean_variables()

        try:
            if step_type in ("psi4_scf", "psi4_hf"):
                from quantumvitas.engines.psi4.runner import run_scf

                # For SCF with save_jk (needed for TD), set it in params
                step_result = run_scf(params=params, working_dir=step_artifacts_dir)

                if not step_result.get("success"):
                    results["error"] = f"SCF step ({step_ulid}) failed: {step_result.get('error', 'Unknown error')}"
                    results["execution_time"] = time.time() - start_time
                    return results

                # Store wfn in state for downstream steps
                state_objects["wfn"] = step_result.get("wfn_object")
                results = step_result

            elif step_type == "psi4_mp2":
                from quantumvitas.engines.psi4.runner import run_mp2

                wfn = state_objects.get("wfn")
                if wfn is None:
                    results["error"] = "MP2 step requires SCF wavefunction, but not found in chain state"
                    results["execution_time"] = time.time() - start_time
                    return results

                step_result = run_mp2(params=params, wfn=wfn, working_dir=step_artifacts_dir)

                if not step_result.get("success"):
                    results["error"] = f"MP2 step ({step_ulid}) failed: {step_result.get('error', 'Unknown error')}"
                    results["execution_time"] = time.time() - start_time
                    return results

                state_objects["wfn"] = step_result.get("wfn_object")
                results = step_result

            elif step_type == "psi4_relax":
                from quantumvitas.engines.psi4.runner import run_relax

                step_result = run_relax(params=params, working_dir=step_artifacts_dir)

                if not step_result.get("success"):
                    results["error"] = f"Relax step ({step_ulid}) failed: {step_result.get('error', 'Unknown error')}"
                    results["execution_time"] = time.time() - start_time
                    return results

                state_objects["wfn"] = step_result.get("wfn_object")
                results = step_result

            elif step_type == "psi4_td":
                from quantumvitas.engines.psi4.runner import run_td

                wfn = state_objects.get("wfn")
                if wfn is None:
                    results["error"] = "TDDFT step requires SCF wavefunction, but not found in chain state"
                    results["execution_time"] = time.time() - start_time
                    return results

                step_result = run_td(params=params, wfn=wfn, working_dir=step_artifacts_dir)

                if not step_result.get("success"):
                    results["error"] = f"TD step ({step_ulid}) failed: {step_result.get('error', 'Unknown error')}"
                    results["execution_time"] = time.time() - start_time
                    return results

                results = step_result

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

        # Write step results.json
        step_results_serializable = {
            k: v for k, v in results.items() if k != "wfn_object"
        }
        step_results_file = step_artifacts_dir / "results.json"
        step_results_file.write_text(
            json.dumps(step_results_serializable, indent=2, default=str)
        )

    results["execution_time"] = time.time() - start_time
    return results
