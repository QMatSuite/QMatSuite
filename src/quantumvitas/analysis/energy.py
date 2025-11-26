"""
Energy summary utilities.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

from quantumvitas.workflow.results import WorkflowResult
from quantumvitas.workflow.workflow import Workflow


def analyze_energies(workflow: Workflow, result: WorkflowResult, results_dir: Path) -> None:
    """
    Extract total energy / Fermi energy metrics from each step result.
    """
    energies: List[Dict[str, object]] = []
    for step in result.steps:
        entry = {
            "step_id": step.step_id,
            "step_type": step.step_type.value,
            "status": step.status.value,
            "total_energy": step.metrics.get("total_energy"),
            "fermi_energy": step.metrics.get("fermi_energy"),
        }
        energies.append(entry)

    (results_dir / "energies.json").write_text(json.dumps(energies, indent=2))

