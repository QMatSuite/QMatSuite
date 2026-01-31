"""
Verification helpers for calculation steps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Optional

from quantumvitas.analysis.energy import extract_energy_metrics_from_text
from .types import StepMode, StepStatus

ENERGY_TOLERANCE = 1e-5  # Rydberg
FERMI_TOLERANCE = 1e-2  # eV (QE reports Fermi in eV)

ENERGY_STEP_TYPES = {"scf", "nscf", "dos", "bandspw"}
FERMI_STEP_TYPES = {"nscf", "dos", "bandspw"}


def basic_job_done_check(output_text: str) -> Tuple[bool, str]:
    if "JOB DONE" in output_text:
        return True, "JOB DONE found in output"
    return False, "JOB DONE not found in output"


def strict_verify(
    step_type: str,
    metrics: Dict[str, float | None],
    output_text: str,
    reference_file: Path,
    tolerance_overrides: Dict[str, float] | None = None,
) -> Tuple[bool, str]:
    """
    Compare against reference output using energy metrics when available.
    """
    if not reference_file.exists():
        return False, f"Reference file not found: {reference_file}"

    reference_metrics = extract_energy_metrics_from_text(reference_file.read_text())
    overrides = tolerance_overrides or {}

    if (
        step_type in ENERGY_STEP_TYPES
        and metrics.get("total_energy_ry") is not None
        and reference_metrics.get("total_energy_ry") is not None
    ):
        tol = overrides.get("total_energy", ENERGY_TOLERANCE)
        diff = abs(metrics["total_energy_ry"] - reference_metrics["total_energy_ry"])
        if diff > tol:
            return (
                False,
                f"Total energy mismatch: Δ={diff:.3e} Ry (tol={tol})",
            )

    if (
        step_type in FERMI_STEP_TYPES
        and metrics.get("fermi_energy_ev") is not None
        and reference_metrics.get("fermi_energy_ev") is not None
    ):
        tol = overrides.get("fermi_energy", FERMI_TOLERANCE)
        diff = abs(metrics["fermi_energy_ev"] - reference_metrics["fermi_energy_ev"])
        if diff > tol:
            return (
                False,
                f"Fermi energy mismatch: Δ={diff:.3e} eV (tol={tol})",
            )

    # Fall back to raw comparison if no metrics are available.
    if reference_file.read_text().strip() == output_text.strip():
        return True, "Output matches reference"
    return True, "Reference comparison passed"


def evaluate_step_result(
    mode: StepMode,
    step_type: str,
    output_text: str,
    reference_file: Path | None,
    step_result_return_code: Optional[int] = None,
    step_result_success: Optional[bool] = None,
) -> Tuple[StepStatus, str, Dict[str, float | None]]:
    """
    Evaluate a step result according to calculation mode.
    
    Args:
        mode: Step execution mode (STRICT or NORMAL)
        step_type: Type of step that was executed
        output_text: Standard output text from the step
        reference_file: Optional reference file for strict verification
        step_result_return_code: Optional return code from step execution (if return_code == 0, step succeeded)
        step_result_success: Optional success flag from step execution (for engines that use results.json)
    
    Returns:
        Tuple of (StepStatus, message, metrics)
    """
    # A. Wannier90 steps should NOT extract energy metrics (no QE output format)
    # Handle both GEN types (wannierprep) and SPEC types (w90_wannierprep, qe_pw2wannier)
    wannier90_gen_types = {"wannierprep", "wannier", "pw2wannier", "wannier90", "postw90"}
    step_type_str = step_type.lower() if step_type else ""
    # Strip engine prefix if present (e.g., "w90_wannierprep" -> "wannierprep")
    if "_" in step_type_str:
        step_type_gen = step_type_str.split("_", 1)[1]
    else:
        step_type_gen = step_type_str

    if step_type_gen in wannier90_gen_types:
        # For Wannier90 steps, don't extract energy metrics
        # Message is based on return_code/result.success + artifact checks (done in run_step())
        metrics: Dict[str, float | None] = {}
        
        if step_result_return_code is not None:
            if step_result_return_code == 0:
                # Success: return code 0 and artifacts validated in run_step()
                return StepStatus.SUCCESS, "Wannier90 step completed successfully (return code 0, artifacts validated)", metrics
            else:
                # Return code non-zero: step failed
                # Error details (stderr) are already in StepResult.error from run_step()
                return StepStatus.FAILED, f"Wannier90 step failed with return code {step_result_return_code}", metrics
        else:
            # Return code not available - this shouldn't happen, but treat as failure
            return StepStatus.FAILED, "Wannier90 step return code not available", metrics
    
    # B. PySCF steps use results.json (not QE output format)
    pyscf_step_types = {"pyscf_scf", "pyscf_rhf", "pyscf_uhf", "pyscf_rks", "pyscf_uks", "pyscf_roks", "pyscf_mp2", "pyscf_td", "pyscf_analysis", "pyscf_freq"}
    if step_type_str in pyscf_step_types:
        # For PySCF steps, use step_result_success (from results.json) or return_code
        metrics: Dict[str, float | None] = {}
        
        # Prefer step_result_success if available (from results.json)
        if step_result_success is not None:
            if step_result_success:
                return StepStatus.SUCCESS, "PySCF step completed successfully (results.json success=True)", metrics
            else:
                return StepStatus.FAILED, "PySCF step failed (results.json success=False)", metrics
        
        # Fallback to return_code if step_result_success not available
        if step_result_return_code is not None:
            if step_result_return_code == 0:
                return StepStatus.SUCCESS, "PySCF step completed successfully (return code 0)", metrics
            else:
                return StepStatus.FAILED, f"PySCF step failed with return code {step_result_return_code}", metrics
        
        # Neither available - treat as failure
        return StepStatus.FAILED, "PySCF step result status not available", metrics
    
    # For QE steps (scf, nscf, etc.), extract energy metrics
    metrics = extract_energy_metrics_from_text(output_text)
    
    # For QE steps (scf, nscf, etc.), check for "JOB DONE" in output
    ok, msg = basic_job_done_check(output_text)
    if not ok:
        # If return code is available and non-zero, include it in message
        if step_result_return_code is not None and step_result_return_code != 0:
            msg += f" [return code: {step_result_return_code}]"
        return StepStatus.FAILED, msg, metrics

    if mode == StepMode.STRICT and reference_file:
        strict_ok, strict_msg = strict_verify(
            step_type=step_type,
            metrics=metrics,
            output_text=output_text,
            reference_file=reference_file,
        )
        if not strict_ok:
            return StepStatus.FAILED, strict_msg, metrics

    return StepStatus.SUCCESS, msg, metrics

