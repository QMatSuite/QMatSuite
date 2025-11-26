"""
Verification helpers for workflow steps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from .types import StepMode, StepStatus, StepType
from .results import StepResultSummary


def basic_job_done_check(output_text: str) -> Tuple[bool, str]:
    if "JOB DONE" in output_text:
        return True, "JOB DONE found in output"
    return False, "JOB DONE not found in output"


def strict_verify(
    step: StepResultSummary,
    reference_file: Path,
    tolerance_overrides: Dict[str, float] | None = None,
) -> Tuple[bool, str]:
    """
    Placeholder strict verification.

    Integration with existing energy/Fermi/frequency extraction can be added here.
    """
    if not reference_file.exists():
        return False, f"Reference file not found: {reference_file}"

    # Minimal behavior: compare raw text equality.
    if reference_file.read_text().strip() == step.output_file.read_text().strip():
        return True, "Output matches reference (byte-for-byte)"
    return False, "Output differs from reference"


def evaluate_step_result(
    mode: StepMode,
    step_type: StepType,
    output_text: str,
    reference_file: Path | None,
) -> Tuple[StepStatus, str]:
    """
    Evaluate a step result according to workflow mode.
    """
    ok, msg = basic_job_done_check(output_text)
    if not ok:
        return StepStatus.FAILED, msg

    if mode == StepMode.STRICT and reference_file:
        # For now defer to simple strict_verify; can plug-in advanced comparison.
        dummy_summary = StepResultSummary(
            step_id="",
            step_type=step_type,
            status=StepStatus.SUCCESS,
            working_dir=reference_file.parent,
            input_file=reference_file,
            output_file=reference_file,
            reference_file=reference_file,
        )
        strict_ok, strict_msg = strict_verify(dummy_summary, reference_file)
        if not strict_ok:
            return StepStatus.FAILED, strict_msg

    return StepStatus.SUCCESS, msg

