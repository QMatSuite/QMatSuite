"""
DOS analysis utilities.
"""

from __future__ import annotations

from pathlib import Path

from quantumvitas.workflow.results import WorkflowResult
from quantumvitas.workflow.workflow import Workflow


def analyze_dos(workflow: Workflow, result: WorkflowResult, results_dir: Path) -> None:
    """
    Locate DOS outputs in ``workflow.raw_dir`` and write processed artifacts.

    This is a placeholder; real implementations can parse QE DOS files and
    produce plots / CSV data.
    """
    dos_steps = [step for step in result.steps if step.step_type.value.startswith("dos")]
    if not dos_steps:
        return

    # For now just record a marker file.
    marker = results_dir / "dos.txt"
    marker.write_text(
        "DOS analysis is not implemented yet. "
        f"Found {len(dos_steps)} DOS steps: {[s.step_id for s in dos_steps]}"
    )

