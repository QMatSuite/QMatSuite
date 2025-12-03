"""
Verification helpers for workflow steps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from quantumvitas.analysis.energy import extract_energy_metrics_from_text
from .types import StepMode, StepStatus, StepType

ENERGY_TOLERANCE = 1e-5  # Rydberg
FERMI_TOLERANCE = 1e-2  # eV (QE reports Fermi in eV)

ENERGY_STEP_TYPES = {
    StepType.SCF,
    StepType.NSCF,
    StepType.DOS,
    StepType.BANDS_PW,
}
FERMI_STEP_TYPES = {
    StepType.NSCF,
    StepType.DOS,
    StepType.BANDS_PW,
}


def basic_job_done_check(output_text: str) -> Tuple[bool, str]:
    if "JOB DONE" in output_text:
        return True, "JOB DONE found in output"
    return False, "JOB DONE not found in output"


def strict_verify(
    step_type: StepType,
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
    step_type: StepType,
    output_text: str,
    reference_file: Path | None,
) -> Tuple[StepStatus, str, Dict[str, float | None]]:
    """
    Evaluate a step result according to workflow mode.
    """
    metrics = extract_energy_metrics_from_text(output_text)
    ok, msg = basic_job_done_check(output_text)
    if not ok:
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

