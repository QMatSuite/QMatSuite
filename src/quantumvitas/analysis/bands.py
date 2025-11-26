"""
Band structure analysis utilities.
"""

from __future__ import annotations

from pathlib import Path

from quantumvitas.workflow.results import WorkflowResult
from quantumvitas.workflow.workflow import Workflow


def analyze_bands(workflow: Workflow, result: WorkflowResult, results_dir: Path) -> None:
    """
    Placeholder band structure analysis.
    """
    band_steps = [
        step for step in result.steps if step.step_type.value.startswith("bands")
    ]
    if not band_steps:
        return

    marker = results_dir / "bands.txt"
    marker.write_text(
        "Band analysis is not implemented yet. "
        f"Found {len(band_steps)} band steps: {[s.step_id for s in band_steps]}"
    )

